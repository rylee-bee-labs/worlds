"""The endpoint manifest: one curated table, verified against live routes.

Product decision #17 (`docs/history/PRODUCT-VISION-HANDOFF.md`, round-2 answers)
makes the API a fully-exposed "Lego box": UI, agent templates and
settings compose against it, so a client needs a machine-readable answer
to "what can I call, and what does calling it cost me in
authorization?". This module is the single curated source for that
answer. `GET /api/manifest` serves it under the `endpoints` key; nothing
else duplicates the table.

Curation source: `docs/surfaces/UI-API-MATRIX.md` +
`docs/surfaces/MASTER-SURFACE-REGISTRY.md` + `docs/surfaces/AUTH-MATRIX.md`
semantics (ids, capability grouping, read/write, gate). Those documents
are prose and drift; the code does not. Every curated row is therefore
**verified against the live FastAPI route table at request time** and
carries `present: false` when the route it names is not registered, so
the manifest can never advertise an endpoint that does not exist.
Routes that exist but are not curated are reported under `uncurated`
with a gate derived from the code — completeness is stated, never
implied.

Vocabulary (deliberately small):

* `kind`: `read` | `write`.
* `gate`: `none` | `step-up` | `proposal` — the *elevation* required
  beyond authentication. `none` means "no elevation gate"; it never
  means "unauthenticated" (see `auth`).
* `auth`: `public` | `authenticated` — whether a credential is required
  at all. `authenticated` is the single `require_auth` entry point (bearer,
  browser session, or the opt-in loopback dev bypass).
* `present`: the route is registered in the running app.

Accuracy note on the enum: a few real writes (`POST /api/vault/set`,
`DELETE /api/vault/{name}`, `POST /api/chat`, `POST /api/setup`) are
gated by `require_auth` only — `docs/surfaces/AUTH-MATRIX.md` records
the Vault ones as a documented divergence from step-up. The three-value
`gate` enum cannot express "authenticated write without elevation", and
claiming `step-up` for them would be a fabrication that sends clients
chasing a grant they do not need. They keep `gate: "none"` and are
listed explicitly, by name, in `writes_without_elevation` — visible
rather than silently normalized. Credential-lifecycle rows (sign-in and
first-run bootstrap: capability `auth`/`setup`, or a `/api/auth/` or
`/api/setup` path) are excluded from that list because they mutate
session/marker state, not world state; they stay fully visible in
`endpoints`/`uncurated` with their real gate and `auth`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

GATES = ("none", "step-up", "proposal")
KINDS = ("read", "write")
AUTH_LEVELS = ("public", "authenticated")

#: Strictness order, used to combine the curated gate with the gate the
#: code actually enforces (see `_effective_gate`).
_GATE_RANK = {gate: rank for rank, gate in enumerate(GATES)}

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Capabilities whose "writes" are credential lifecycle rather than
# world-state mutation (see `endpoint_manifest`).
_CREDENTIAL_CAPABILITIES = frozenset({"auth", "setup"})
_CREDENTIAL_PATH_PREFIXES = ("/api/auth/", "/api/setup")


@dataclass(frozen=True)
class Endpoint:
    """One curated (method, path) row of the endpoint manifest."""

    id: str
    method: str
    path: str
    capability: str
    kind: str
    gate: str
    auth: str = "authenticated"
    note: str | None = None

    def __post_init__(self) -> None:
        # Fail at import, loudly, rather than serve a malformed manifest.
        if self.kind not in KINDS:
            raise ValueError(f"{self.id}: kind must be one of {KINDS}")
        if self.gate not in GATES:
            raise ValueError(f"{self.id}: gate must be one of {GATES}")
        if self.auth not in AUTH_LEVELS:
            raise ValueError(f"{self.id}: auth must be one of {AUTH_LEVELS}")
        if self.method.upper() in _READ_METHODS and self.kind == "write":
            raise ValueError(f"{self.id}: a {self.method} cannot be a write")
        if (
            self.method.upper() not in _READ_METHODS
            and self.kind == "read"
            and not self.note
        ):
            # A mutating verb may be curated as a read only when the row
            # says why (an outbound probe that changes no local state).
            # An accidental one fails at import instead of shipping.
            raise ValueError(
                f"{self.id}: {self.method} is a write method; declare it "
                "kind='write', or justify kind='read' with a note"
            )


def _e(
    id: str,
    method: str,
    path: str,
    capability: str,
    kind: str,
    gate: str,
    auth: str = "authenticated",
    note: str | None = None,
) -> Endpoint:
    return Endpoint(
        id=id,
        method=method.upper(),
        path=path,
        capability=capability,
        kind=kind,
        gate=gate,
        auth=auth,
        note=note,
    )


# ── The curated table ────────────────────────────────────────────────
# Ordered by capability, mirroring the UI-API-MATRIX grouping. `id`
# reuses the surface-registry id; a suffix is added only where one
# registry id covers several (method, path) pairs.
ENDPOINTS: tuple[Endpoint, ...] = (
    # Bootstrap / liveness — the only genuinely public rows.
    _e("API-001", "GET", "/healthz", "health", "read", "none", "public"),
    _e("API-002-status", "GET", "/api/setup/status", "setup", "read", "none", "public"),
    _e(
        "API-002-run",
        "POST",
        "/api/setup",
        "setup",
        "write",
        "none",
        "public",
        "first-run bootstrap; loopback-only (403 otherwise); 409 once "
        "the setup-complete marker exists",
    ),
    # Browser session (auth_routes.py; registry family AUTH-009).
    _e(
        "AUTH-009-login",
        "POST",
        "/api/auth/login",
        "auth",
        "write",
        "none",
        "public",
        "exchanges a credential for a session cookie",
    ),
    _e(
        "AUTH-009-logout", "POST", "/api/auth/logout", "auth", "write", "none", "public"
    ),
    _e(
        "AUTH-009-session", "GET", "/api/auth/session", "auth", "read", "none", "public"
    ),
    _e(
        "AUTH-009-step-up",
        "POST",
        "/api/auth/step-up",
        "auth",
        "write",
        "none",
        "public",
        "mints the time-bounded, principal-bound elevation that "
        "gate='step-up' routes consume",
    ),
    _e(
        "AUTH-009-oidc-config",
        "GET",
        "/api/auth/oidc/config",
        "auth",
        "read",
        "none",
        "public",
    ),
    _e(
        "AUTH-009-oidc-login",
        "GET",
        "/api/auth/oidc/login",
        "auth",
        "read",
        "none",
        "public",
    ),
    _e(
        "AUTH-009-oidc-step-up",
        "GET",
        "/api/auth/oidc/step-up",
        "auth",
        "read",
        "none",
        "public",
        "confirm it's you by a fresh provider sign-in; the callback grants "
        "step-up only for the same person with a recent auth_time",
    ),
    _e(
        "AUTH-009-oidc-link",
        "POST",
        "/api/auth/oidc/link",
        "auth",
        "write",
        "step-up",
        note="signed-in person links a provider sign-in to their own "
        "account; same-origin; the callback links only if the same "
        "person is still signed in",
    ),
    _e(
        "AUTH-009-oidc-callback",
        "GET",
        "/api/auth/oidc/callback",
        "auth",
        "read",
        "none",
        "public",
    ),
    # World / daily loop.
    _e("API-003", "GET", "/api/status", "world", "read", "none"),
    _e(
        "API-004-get",
        "GET",
        "/api/daily",
        "daily",
        "read",
        "none",
        note="read-only digest; never mutates",
    ),
    _e(
        "API-004-post",
        "POST",
        "/api/daily",
        "daily",
        "write",
        "none",
        note="runs the daily loop: journals observations, records facts, "
        "saves world.json — authenticated, not elevation-gated",
    ),
    _e("API-014", "GET", "/api/actors", "world", "read", "none"),
    _e(
        "API-015",
        "GET",
        "/api/manifest",
        "manifest",
        "read",
        "none",
        note="data = capability/provider manifest; endpoints = this table",
    ),
    _e("API-075", "POST", "/api/world/intent", "world", "write", "step-up"),
    _e("API-076-fact", "POST", "/api/world/fact", "world", "write", "step-up"),
    _e(
        "API-076-policy",
        "POST",
        "/api/world/policy",
        "world",
        "write",
        "step-up",
        note="cemented policies still refuse (409)",
    ),
    # Journal.
    _e(
        "API-005",
        "GET",
        "/api/journal",
        "journal",
        "read",
        "none",
        note="current version of each chain; person principals only",
    ),
    _e(
        "API-006",
        "POST",
        "/api/journal",
        "journal",
        "write",
        "none",
        note="personal note append; authenticated, not elevation-gated",
    ),
    _e(
        "API-007",
        "POST",
        "/api/journal/supersede",
        "journal",
        "write",
        "step-up",
        note="append-only correction",
    ),
    _e("API-008", "GET", "/api/journal/history", "journal", "read", "none"),
    _e("API-084", "GET", "/api/journal/last", "journal", "read", "none",
       note="newest CURRENT entry (calm-view tail) for the daily home "
            "loop's thread deep-link; null when empty; person "
            "principals only"),
    # Worlds briefing / place continuity (contract: worlds-briefing/1).
    _e("API-085", "GET", "/api/briefing", "briefing", "read", "none",
       note="the world's briefing (six systems, have_tos, arrivals, "
            "thread); read-only, never writes the journal; person "
            "principals only"),
    _e("API-086", "GET", "/api/place", "briefing", "read", "none",
       note="the caller's last place (continuity); person principals only"),
    _e("API-087", "PUT", "/api/place", "briefing", "write", "none",
       note="stores the caller's last place; authenticated, not "
            "elevation-gated; person principals only"),
    # Rooms — the main app renders other small backends (room/0).
    # Read-only: it fetches each configured room outbound and never
    # mutates local state; an unreachable room is reported, not raised.
    _e("API-088", "GET", "/api/rooms", "rooms", "read", "none",
       note="the estate's rooms (contract room/0): each configured "
            "backend's descriptor, cards, needs-you, reachability and "
            "persisted last-seen, plus the caller's private visit state "
            "(last_visited_at, needs_seen, changed_since_visit) with "
            "resume/summary siblings of data; never raises, never claims "
            "an unreachable room healthy. The room list is read at "
            "runtime from Project Home's registry when PW_ROOMS_REGISTRY_URL "
            "is set (cached 60 s, last-known-good persisted, env fallback) "
            "and a sibling `registry` states its source/status; a room "
            "whose contract Worlds does not support is "
            "`incompatible`, never healthy, with its cards/needs uncounted; "
            "each row carries an optional `public_url` (a registry entry's "
            "browser-reachable http(s) address, no userinfo) or "
            "null when absent/invalid. A registry room may opt in to "
            "per-person forwarding (`forward_principal`, with its own "
            "token): its cards/needs are then fetched and cached 15 s per "
            "caller (bounded) while its status/reachability/last-seen stay "
            "estate-wide; one caller's forwarded cards/needs never appear "
            "in another's response"),
    _e("API-088-visit", "POST", "/api/rooms/{room_id}/visit", "rooms",
       "write", "none",
       note="Worlds-owned, caller-scoped visit state (never sent to a "
            "room): sets last_visited_at + resume; idempotent; 404 for "
            "an unconfigured room, 422 for a non-same-origin link; "
            "authenticated, not elevation-gated like drafts/place"),
    _e("API-088-need-seen", "POST", "/api/rooms/{room_id}/needs/{need_id}/seen",
       "rooms", "write", "none",
       note="marks one need seen for the caller (caller-scoped, "
            "deduped/capped); idempotent; 404 for an unconfigured room"),
    _e("API-088-keeper", "PUT", "/api/rooms/{room_id}/keeper", "rooms",
       "write", "none",
       note="the caller's keeper for one configured room "
            "({companion_id} or null): one keeper per room, a companion "
            "may keep several; 404 for an unconfigured room, 422 for an "
            "unknown companion; records who the person put there and "
            "never the room's status"),
    _e("API-088-doorway", "PUT", "/api/rooms/{room_id}/doorway", "rooms",
       "write", "none",
       note="the caller's doorway for one configured room ({doorway_id} "
            "from the closed list, or null): presentation only, private, "
            "never sent to the room and never the room's status; 404 for "
            "an unconfigured room, 422 for an id outside the closed list"),
    _e("API-088-action", "POST", "/api/rooms/{room_id}/actions/{action_id}",
       "rooms", "write", "none",
       note="pass one room/0 action through to its room and return the "
            "room's own receipt ({action_id, ok, summary, changed, at}) "
            "with HTTP 200 whatever the room's status; a room that cannot "
            "answer yields an ok:false 'nothing changed' receipt, "
            "never a 500. Owner-only for writes: the room's own GET "
            "/room/actions list (cached 60 s per room) decides whether the "
            "action exists (404 otherwise) and whether it writes (a write "
            "needs the approve permission, 403 otherwise; a missing writes "
            "field fails closed as a write). Requires an Idempotency-Key "
            "(1-128 chars, 400 when missing) and a JSON object body of at "
            "most 16 KB (413/400 otherwise), forwarded as-is with the "
            "room's own token, the caller's X-Worlds-Principal, and that "
            "key — never the human session or PW_API_TOKEN; a successful "
            "action drops the cached snapshot so the need disappears on "
            "the next GET /api/rooms; authenticated, not elevation-gated"),
    # Secrets overview — the Worlds side of the read-only Secrets board.
    # It finds the `workshop` registry room and reads that room's
    # read-only /api/secrets/summary with the room's own token/TLS policy
    # (3 s timeout, 60 s cache). Names and health only — never a value.
    _e("API-090", "GET", "/api/secrets/overview", "secrets", "read", "none",
       note="the Secrets board's data source: reads the `workshop` registry "
            "room's read-only /api/secrets/summary (3 s timeout, 60 s "
            "cache) with that room's token/TLS policy; names and health "
            "only, never a secret value; a missing/unreachable/refusing/"
            "malformed station is reported as station.status 'unknown' with "
            "a plain-words detail and empty lists — never raises, never "
            "invents keys, never carries a token; estate_secrets-gated in "
            "handler"),
    # Crew — companions are user-owned (owner decision 2026-09-25). The
    # drawn crew is a starter set; a person adds, renames, hides and
    # deletes their own. Private, per principal, never sent to a room or
    # a model. Same per-principal entry point as rooms visits; no new store.
    _e("API-089", "GET", "/api/crew", "crew", "read", "none",
       note="the caller's own crew (private, per principal), "
            "starter-seeded on first read; includes hidden entries so "
            "Worlds decides what to filter"),
    _e("API-089-create", "POST", "/api/crew", "crew", "write", "none",
       note="{name, blurb?, voice_label?} → source 'user', id = a unique "
            "slug of the name; strings only, name ≤ 60 / blurb ≤ 280 / "
            "voice_label ≤ 60"),
    _e("API-089-patch", "PATCH", "/api/crew/{companion_id}", "crew",
       "write", "none",
       note="rename/reword/hide one companion (the drawn crew included); "
            "omitted keys untouched, null clears an optional text field; "
            "404 for an unknown companion"),
    _e("API-089-delete", "DELETE", "/api/crew/{companion_id}", "crew",
       "write", "none",
       note="deletes the caller's own companion and clears the keeper "
            "assignments it held; 409 for a starter (hide it instead)"),
    _e("API-089-portrait-put", "POST", "/api/crew/{companion_id}/portrait",
       "crew", "write", "none",
       note="{content_type, data_base64}: image/png|jpeg|webp verified by "
            "magic bytes (415 on a mismatch), decoded ≤ 5 MB (413), "
            "stored 0600 in the caller's scoped data dir — no new store, "
            "no new dependency; the bytes never travel to a room or a "
            "model"),
    _e("API-089-portrait-get", "GET", "/api/crew/{companion_id}/portrait",
       "crew", "read", "none",
       note="serves an uploaded portrait same-origin with its real media "
            "type, Cache-Control: private and "
            "X-Content-Type-Options: nosniff; 404 when none is uploaded"),
    _e("API-089-portrait-delete", "DELETE",
       "/api/crew/{companion_id}/portrait", "crew", "write", "none",
       note="removes an uploaded portrait; a drawn companion falls back "
            "to its shipped portrait path, a person's own falls back to "
            "none; 404 when there is nothing uploaded"),
    # journal drafts — lining rescue (D15 "kept safe, synced"); no elevation
    # by design: a draft mutates nothing a publish doesn't already change.
    _e("API-080", "PUT", "/api/journal/draft", "journal", "write", "none",
       note="debounced client drafts; response never echoes text"),
    _e("API-081", "GET", "/api/journal/draft", "journal", "read", "none",
       note="resume-on-any-device read of the caller's own draft"),
    _e("API-082", "DELETE", "/api/journal/draft", "journal", "write", "none",
       note="cleared after confirmed publish"),
    _e("API-083", "POST", "/api/journal/edit-pair", "journal", "write", "none",
       note="edit-pair capture v0 (§capture lineage); response never "
            "echoes content"),
    _e("API-009", "GET", "/api/journal/audit", "journal", "read", "none"),
    _e("API-016", "GET", "/api/memory/search", "memory", "read", "none"),
    # Chat / brain.
    _e(
        "API-010",
        "POST",
        "/api/chat",
        "chat",
        "write",
        "none",
        note="read-only over a world snapshot, but can journal a "
        "recommendation event and create proposals",
    ),
    _e("API-011", "GET", "/api/chat/providers", "chat", "read", "none"),
    _e(
        "API-010-history",
        "GET",
        "/api/chat/history",
        "chat",
        "read",
        "none",
        note="the caller's own persisted transcript, oldest first "
        "(per-user, decision #13)",
    ),
    _e(
        "API-012",
        "POST",
        "/api/chat/test",
        "chat",
        "read",
        "none",
        note="POST verb, but a provider probe: it changes no local state "
        "(it does spend provider quota)",
    ),
    _e("API-013", "GET", "/api/tools", "tools", "read", "none"),
    _e("API-077-templates", "GET", "/api/brain/templates", "brain", "read", "none"),
    _e("API-077-provenance", "GET", "/api/brain/provenance", "brain", "read", "none"),
    _e(
        "API-077-discovery",
        "GET",
        "/api/templates",
        "brain",
        "read",
        "none",
        note="public discovery view {id, surface, role, description} with "
        "overrides applied; API-077-templates carries the full metadata",
    ),
    # Proposals — the propose → approve → act lifecycle. The registry
    # has no API-nnn id for this family; PROP-* is minted here and is
    # the canonical machine id.
    _e("PROP-list", "GET", "/api/proposals", "proposals", "read", "none"),
    _e("PROP-get", "GET", "/api/proposals/{proposal_id}", "proposals", "read", "none"),
    _e(
        "PROP-approve",
        "POST",
        "/api/proposals/{proposal_id}/approve",
        "proposals",
        "write",
        "step-up",
        note="owner approval; evidence is server-held and persisted",
    ),
    _e(
        "PROP-reject",
        "POST",
        "/api/proposals/{proposal_id}/reject",
        "proposals",
        "write",
        "step-up",
    ),
    _e(
        "PROP-execute",
        "POST",
        "/api/proposals/{proposal_id}/execute",
        "proposals",
        "write",
        "proposal",
        note="acts only on a proposal already approved through "
        "PROP-approve; a model cannot invoke it",
    ),
    # Preferences / layout / apps / themes.
    _e("API-030-get", "GET", "/api/prefs", "prefs", "read", "none"),
    _e(
        "API-030-put",
        "PUT",
        "/api/prefs",
        "prefs",
        "write",
        "none",
        note="own-account write: signed-in person only, no step-up",
    ),
    _e(
        "API-030-patch",
        "PATCH",
        "/api/prefs",
        "prefs",
        "write",
        "none",
        note="alias of API-030-put: the same partial update, the same gate "
        "(the handler has always applied exactly the keys it was given)",
    ),
    _e("API-031", "GET", "/api/prefs/schema", "prefs", "read", "none"),
    _e("API-032-get", "GET", "/api/sections", "sections", "read", "none"),
    _e("API-032-put", "PUT", "/api/sections", "sections", "write", "step-up"),
    _e("API-066-get", "GET", "/api/apps", "apps", "read", "none"),
    _e("API-066-put", "PUT", "/api/apps", "apps", "write", "step-up"),
    _e("API-065-list", "GET", "/api/themes", "themes", "read", "none"),
    _e("API-065-get", "GET", "/api/themes/{name}", "themes", "read", "none"),
    # Reminders / scheduler.
    _e("API-067-get", "GET", "/api/reminders", "reminders", "read", "none"),
    _e("API-067-add", "POST", "/api/reminders", "reminders", "write", "step-up"),
    _e(
        "API-067-toggle",
        "PATCH",
        "/api/reminders/{rid}",
        "reminders",
        "write",
        "step-up",
    ),
    _e(
        "API-067-delete",
        "DELETE",
        "/api/reminders/{rid}",
        "reminders",
        "write",
        "step-up",
    ),
    # Connections & providers.
    _e("API-017", "GET", "/api/connections/schemas", "connections", "read", "none"),
    _e(
        "API-018",
        "GET",
        "/api/connections/schema/{capability}",
        "connections",
        "read",
        "none",
    ),
    _e("API-019", "GET", "/api/connections/config", "connections", "read", "none"),
    _e("API-020", "GET", "/api/connections/overview", "connections", "read", "none"),
    _e("API-021-list", "GET", "/api/connections", "connections", "read", "none"),
    _e("API-021-save", "PUT", "/api/connections", "connections", "write", "step-up"),
    _e(
        "API-021-delete",
        "DELETE",
        "/api/connections/{name}",
        "connections",
        "write",
        "step-up",
    ),
    _e(
        "API-022",
        "POST",
        "/api/connections/config/{key}",
        "connections",
        "write",
        "step-up",
    ),
    _e(
        "API-023",
        "POST",
        "/api/connections/test",
        "connections",
        "read",
        "none",
        note="POST verb, but a live outbound probe: it changes no local state",
    ),
    _e(
        "API-024",
        "POST",
        "/api/connections/validate",
        "connections",
        "read",
        "none",
        note="POST verb, but a live outbound probe: it changes no local state",
    ),
    # Source control / projects / ingress.
    _e(
        "API-033", "GET", "/api/source-control/status", "source_control", "read", "none"
    ),
    _e(
        "API-034",
        "GET",
        "/api/source-control/history",
        "source_control",
        "read",
        "none",
    ),
    _e(
        "API-035",
        "POST",
        "/api/source-control/refresh",
        "source_control",
        "write",
        "step-up",
        note="the propose→approve→act refresh workflow; the elevation "
        "gate is require_step_up in code",
    ),
    _e(
        "API-036",
        "GET",
        "/api/source-control/enrichment",
        "source_control",
        "read",
        "none",
    ),
    _e("API-079", "GET", "/api/projects/status", "projects", "read", "none"),
    _e("API-078", "GET", "/api/ingress/rollups", "ingress", "read", "none"),
    # Lab (external CLI packets + native lab).
    _e("API-037", "GET", "/api/lab/state", "lab", "read", "none"),
    _e("API-038", "GET", "/api/lab/settings", "lab", "read", "none"),
    _e("API-039", "GET", "/api/lab/settings/inspect/{service}", "lab", "read", "none"),
    _e("API-040", "GET", "/api/lab/settings/diff/{service}", "lab", "read", "none"),
    _e("API-041", "GET", "/api/lab/health", "lab", "read", "none"),
    _e("API-042", "GET", "/api/lab/deploy", "lab", "read", "none"),
    _e(
        "API-043",
        "GET",
        "/api/lab/secrets",
        "lab",
        "read",
        "none",
        note="secret names/metadata only; never resolved values",
    ),
    _e("API-044", "GET", "/api/lab/resources", "lab", "read", "none"),
    _e("API-058", "GET", "/api/reconciler/status", "reconciler", "read", "none"),
    _e(
        "API-059", "GET", "/api/reconciler/diff/{service}", "reconciler", "read", "none"
    ),
    _e(
        "API-060",
        "GET",
        "/api/reconciler/propose/{service}",
        "reconciler",
        "read",
        "none",
        note="propose only; never applies",
    ),
    _e("API-053", "GET", "/api/media/status", "media", "read", "none"),
    _e("API-054", "GET", "/api/media/library", "media", "read", "none"),
    _e("API-055", "GET", "/api/media/recent", "media", "read", "none"),
    _e("API-056", "GET", "/api/media/activity", "media", "read", "none"),
    _e("API-057", "GET", "/api/media/search", "media", "read", "none"),
    # Vault — see the AUTH-MATRIX divergence note in this docstring.
    _e("API-061", "GET", "/api/vault/status", "vault", "read", "none"),
    _e(
        "API-062-unlock",
        "POST",
        "/api/vault/unlock",
        "vault",
        "write",
        "none",
        note="requires the master passphrase in the body",
    ),
    _e("API-062-lock", "POST", "/api/vault/lock", "vault", "write", "none"),
    _e(
        "API-063-names",
        "GET",
        "/api/vault/names",
        "vault",
        "read",
        "none",
        note="names only; requires an unlocked vault",
    ),
    _e(
        "API-063-set",
        "POST",
        "/api/vault/set",
        "vault",
        "write",
        "none",
        note="documented divergence: bearer/session auth, not step-up",
    ),
    _e(
        "API-064-get",
        "GET",
        "/api/vault/{name}",
        "vault",
        "read",
        "none",
        note="value read; additionally peer-address restricted and journaled name-only",
    ),
    _e(
        "API-064-delete",
        "DELETE",
        "/api/vault/{name}",
        "vault",
        "write",
        "none",
        note="documented divergence: bearer/session auth, not step-up",
    ),
    # Identity / ownership.
    _e(
        "API-068-list",
        "GET",
        "/api/identity/users",
        "identity",
        "read",
        "none",
        note="manage_people-gated in handler",
    ),
    _e(
        "API-069",
        "POST",
        "/api/identity/users",
        "identity",
        "write",
        "step-up",
        note="manage_people-gated in handler",
    ),
    _e(
        "API-070",
        "DELETE",
        "/api/identity/users/{user_id}",
        "identity",
        "write",
        "step-up",
        note="manage_people-gated in handler",
    ),
    _e(
        "API-071-get",
        "GET",
        "/api/identity/agents",
        "identity",
        "read",
        "none",
        note="ownership-filtered",
    ),
    _e(
        "API-071-create", "POST", "/api/identity/agents", "identity", "write", "step-up"
    ),
    _e(
        "API-072",
        "DELETE",
        "/api/identity/agents/{agent_id}",
        "identity",
        "write",
        "step-up",
    ),
    _e(
        "API-071-viewers-get",
        "GET",
        "/api/identity/viewers",
        "identity",
        "read",
        "none",
        note="owner only; read-only credentials listed without hashes or tokens",
    ),
    _e(
        "API-071-viewers-create",
        "POST",
        "/api/identity/viewers",
        "identity",
        "write",
        "step-up",
        note="owner only; mints a read-only credential (GET/HEAD/OPTIONS as the "
        "owner, never step-up); token shown once",
    ),
    _e(
        "API-071-viewers-delete",
        "DELETE",
        "/api/identity/viewers/{viewer_id}",
        "identity",
        "write",
        "step-up",
        note="owner only; revokes a read-only credential",
    ),
    _e("API-073", "GET", "/api/identity/principal", "identity", "read", "none"),
    _e(
        "API-074",
        "PUT",
        "/api/identity/principal",
        "identity",
        "write",
        "none",
        note="own-account write: signed-in person only, no step-up",
    ),
    # People & roles (owner-approved 2026-09-26): code asks
    # `roles.can(principal, permission)`; admins manage accounts, never
    # content. Responses are allow-listed (no secrets, no tokens).
    _e(
        "API-091",
        "GET",
        "/api/me",
        "identity",
        "read",
        "none",
        note="the caller's own {id, display_name, role, permissions} "
        "for the interface to show/hide affordances",
    ),
    _e(
        "API-092",
        "GET",
        "/api/people",
        "identity",
        "read",
        "none",
        note="every person and agent with role/kind; manage_people-gated "
        "in handler; no content, secrets or tokens",
    ),
    _e(
        "API-093",
        "PUT",
        "/api/people/{user_id}/role",
        "identity",
        "write",
        "step-up",
        note="manage_people-gated; sets member/supervised/guest/admin; "
        "owner never assignable (422), admins cannot change their own "
        "role (403), the owner record is protected (403)",
    ),
    _e(
        "API-094",
        "POST",
        "/api/people/transfer-ownership",
        "identity",
        "write",
        "step-up",
        note="owner only (transfer_ownership); target must already be an "
        "admin; the old owner becomes an admin; journalled",
    ),
    # People screens step 2 (owner-approved 2026-09-26): invites, helper
    # grants, supervised limits, guests. Identity-level metadata; no route
    # reads another person's content.
    _e(
        "API-095-list",
        "GET",
        "/api/people/invites",
        "identity",
        "read",
        "none",
        note="open invite links (role, who for, expiry, used?); "
        "manage_people-gated; never a token or hash",
    ),
    _e(
        "API-095-create",
        "POST",
        "/api/people/invites",
        "identity",
        "write",
        "step-up",
        note="manage_people-gated; {role, display_name, "
        "expires_in_hours?, guest_until?}; the one-time token is returned "
        "once and only its hash is stored; the owner is never invitable "
        "(422) and only the owner may invite an admin (403)",
    ),
    _e(
        "API-095-delete",
        "DELETE",
        "/api/people/invites/{invite_id}",
        "identity",
        "write",
        "step-up",
        note="cancel an invite link; manage_people-gated",
    ),
    _e(
        "API-096",
        "POST",
        "/api/invites/accept",
        "identity",
        "write",
        "none",
        "public",
        "accept a one-time link: {token} creates the local "
        "account with the invite's role; single-use and expiry enforced; "
        "returns a random sign-in key once; only its hash is stored",
    ),
    _e(
        "API-097-list",
        "GET",
        "/api/me/helpers",
        "identity",
        "read",
        "none",
        note="grants the caller issued, including revoked ones so an "
        "owner's emergency revocation stays visible",
    ),
    _e(
        "API-097-grant",
        "POST",
        "/api/me/helpers",
        "identity",
        "write",
        "step-up",
        note="a person grants helper access: {helper_id, can_act?, "
        "until?}; until must be a future ISO time within 30 days "
        "(default 7); the person grants, never an admin",
    ),
    _e(
        "API-097-revoke",
        "DELETE",
        "/api/me/helpers/{grant_id}",
        "identity",
        "write",
        "step-up",
        note="revoke a grant any time; the person who granted it, or the "
        "owner in an emergency (journalled and visible to the person)",
    ),
    _e(
        "API-098",
        "GET",
        "/api/me/helped-by",
        "identity",
        "read",
        "none",
        note="what helpers did for the caller, newest first: "
        "{at, helper_id, action, summary, undoable}; undoable is false "
        "unless a room's own receipt says otherwise",
    ),
    _e(
        "API-099-get",
        "GET",
        "/api/me/limits",
        "identity",
        "read",
        "none",
        note="the caller's own supervised limits and who set them; "
        "empty when none",
    ),
    _e(
        "API-099-put",
        "PUT",
        "/api/people/{user_id}/limits",
        "identity",
        "write",
        "step-up",
        note="manage_people or a guardian (a live can_act helper grant) "
        "sets {limits: [{key, value}]} from the closed set "
        "(chat_quiet_hours, no_outside_sharing, content_boundary); who "
        "set it and when are stored; a guardian still cannot read the "
        "person's journal or world",
    ),
    _e(
        "API-100",
        "GET",
        "/api/people/directory",
        "identity",
        "read",
        "none",
        note="people picker: [{id, display_name}] for enabled people "
        "only, no roles, emails, expired guests or agents; gated on "
        "own_space (people who live here), so guests and agents get 403",
    ),
    # Web Push & notifications (the notifications transport; docs/NOTIFICATIONS.md).
    # Device self-registration and personal history are the caller's own
    # surface: auth-only, never step-up (a phone setting itself up has no
    # session grant yet), and person-only (an agent publishes through
    # API-103, it never reads a person's devices).
    _e(
        "API-101-key",
        "GET",
        "/api/push/public-key",
        "notifications",
        "read",
        "none",
        note="the VAPID public key a browser subscribes with; 409 "
        "not_configured when push has no key here",
    ),
    _e(
        "API-101-add",
        "POST",
        "/api/push/subscriptions",
        "notifications",
        "write",
        "none",
        note="register/refresh one device (upsert by endpoint); the "
        "endpoint + keys are stored per person and never returned",
    ),
    _e(
        "API-101-list",
        "GET",
        "/api/push/subscriptions",
        "notifications",
        "read",
        "none",
        note="device labels and times only, never keys or endpoints",
    ),
    _e(
        "API-101-del",
        "DELETE",
        "/api/push/subscriptions/{sub_id}",
        "notifications",
        "write",
        "none",
    ),
    _e(
        "API-102-list",
        "GET",
        "/api/notifications",
        "notifications",
        "read",
        "none",
        note="the caller's history, newest first; unread=1 and limit",
    ),
    _e(
        "API-102-prefs-get",
        "GET",
        "/api/notifications/prefs",
        "notifications",
        "read",
        "none",
    ),
    _e(
        "API-102-prefs-put",
        "PUT",
        "/api/notifications/prefs",
        "notifications",
        "write",
        "none",
        note="tiers/sources/quiet hours; quiet hours are ON by default "
        "21:00-08:00 and when_ready never pushes unless turned on",
    ),
    _e(
        "API-102-read",
        "POST",
        "/api/notifications/{note_id}/read",
        "notifications",
        "write",
        "none",
    ),
    _e(
        "API-102-read-all",
        "POST",
        "/api/notifications/read-all",
        "notifications",
        "write",
        "none",
    ),
    _e(
        "API-102-test",
        "POST",
        "/api/notifications/test",
        "notifications",
        "write",
        "none",
        note="'send me a test' to the caller's own devices; not step-up "
        "because it reaches no state",
    ),
    _e(
        "API-103",
        "POST",
        "/api/notify",
        "notifications",
        "write",
        "none",
        note="publishing door for agents/CLI: a person notifies "
        "themselves; an agent needs the notify scope (recipient is its "
        "owner; another person only when the owner has manage_people). "
        "30/min per caller, idempotent on dedupe_key for a day",
    ),
    # Exports / backup / updates.
    _e(
        "API-025",
        "GET",
        "/api/exports/settings",
        "exports",
        "read",
        "none",
        note="shareable blueprint; never personal data",
    ),
    _e(
        "API-026",
        "GET",
        "/api/exports/world",
        "exports",
        "read",
        "none",
        note="portable personal config; never secrets or private lore",
    ),
    _e("API-027", "GET", "/api/exports/story", "exports", "read", "none"),
    _e(
        "API-028",
        "GET",
        "/api/backup",
        "exports",
        "read",
        "none",
        note="includes private state; encrypt externally, never share",
    ),
)


def _route_index(routes: Iterable[Any]) -> dict[tuple[str, str], set[str]]:
    """(METHOD, path) → the auth dependency names the code declares."""

    def walk(dependant: Any, into: set[str]) -> None:
        call = getattr(dependant, "call", None)
        if call is not None:
            into.add(getattr(call, "__name__", ""))
        for sub in getattr(dependant, "dependencies", []) or ():
            walk(sub, into)

    index: dict[tuple[str, str], set[str]] = {}
    for route in routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        names: set[str] = set()

        dependant = getattr(route, "dependant", None)
        if dependant is not None:
            try:
                walk(dependant, names)
            except Exception:  # nosec B110  # introspection must never break the manifest
                pass
        for method in methods:
            index.setdefault((method.upper(), path), set()).update(names)
    return index


def _effective_gate(row: Endpoint, deps: set[str]) -> str:
    """The stricter of what the code declares and what curation declares.

    A dependency-level `require_step_up` outranks a curated `none`: code
    is truth, and curation can never advertise a write as ungated. A
    curated `proposal` outranks a code-declared `step-up`, because the
    proposal lifecycle *includes* that elevation and adds the
    approved-proposal evidence check on top — reporting only `step-up`
    would understate what the caller needs. Curation is also the only
    place an in-handler step-up check can be expressed.
    """
    declared = "step-up" if "require_step_up" in deps else "none"
    return declared if _GATE_RANK[declared] > _GATE_RANK[row.gate] else row.gate


def _effective_auth(row: Endpoint, deps: set[str]) -> str:
    if deps & {"require_auth", "require_step_up"}:
        return "authenticated"
    return row.auth


def _serialize(
    row: Endpoint, *, present: bool, gate: str, auth: str, curated: bool
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": row.id if curated else None,
        "method": row.method,
        "path": row.path,
        "capability": row.capability,
        "kind": row.kind,
        "gate": gate,
        "auth": auth,
        "present": present,
    }
    if row.note:
        out["note"] = row.note
    return out


def _kind_for(method: str) -> str:
    return "read" if method.upper() in _READ_METHODS else "write"


def endpoint_manifest(routes: Iterable[Any]) -> dict[str, Any]:
    """Build the endpoint manifest, verified against `routes`.

    `routes` is any iterable of Starlette routes (pass `app.routes`).
    The result is JSON-serializable and carries no credential material,
    no filesystem paths and no configuration values — only route
    shapes and authorization labels.
    """
    index = _route_index(routes)

    endpoints: list[dict[str, Any]] = []
    writes_without_elevation: list[str] = []
    missing: list[str] = []
    curated_keys: set[tuple[str, str]] = set()

    for row in ENDPOINTS:
        key = (row.method, row.path)
        curated_keys.add(key)
        deps = index.get(key, set())
        present = key in index
        gate = _effective_gate(row, deps)
        auth = _effective_auth(row, deps) if present else row.auth
        endpoints.append(
            _serialize(row, present=present, gate=gate, auth=auth, curated=True)
        )
        label = f"{row.method} {row.path}"
        if not present:
            missing.append(label)
        # Credential-lifecycle rows (sign in/out, first-run bootstrap) are
        # mutating verbs but not world-state writes; listing them here
        # would drown the rows that actually matter. They remain fully
        # visible in `endpoints` with gate="none", auth="public".
        if (
            row.kind == "write"
            and gate == "none"
            and row.capability not in _CREDENTIAL_CAPABILITIES
        ):
            writes_without_elevation.append(label)

    # Live routes that this table does not curate. Reported with a
    # code-derived gate so the manifest states its own coverage instead
    # of implying completeness. Non-API machinery (docs, static assets,
    # the SPA fallback) is excluded: it is not part of the Lego box.
    uncurated: list[dict[str, Any]] = []
    for (method, path), deps in sorted(index.items()):
        if (method, path) in curated_keys:
            continue
        if method in ("HEAD", "OPTIONS"):
            continue
        if not path.startswith("/api/"):
            continue
        gate = "step-up" if "require_step_up" in deps else "none"
        auth = (
            "authenticated" if deps & {"require_auth", "require_step_up"} else "public"
        )
        kind = _kind_for(method)
        row = Endpoint(
            id="",
            method=method,
            path=path,
            capability="uncurated",
            kind=kind,
            gate=gate,
            auth=auth,
        )
        uncurated.append(
            _serialize(row, present=True, gate=gate, auth=auth, curated=False)
        )
        if (
            kind == "write"
            and gate == "none"
            and not path.startswith(_CREDENTIAL_PATH_PREFIXES)
        ):
            writes_without_elevation.append(f"{method} {path}")

    return {
        "source": "src/personal_world/api_manifest.py (curated from "
        "docs/surfaces/UI-API-MATRIX.md + MASTER-SURFACE-REGISTRY"
        ".md + AUTH-MATRIX.md), verified against the live route "
        "table",
        "vocabulary": {
            "kind": list(KINDS),
            "gate": list(GATES),
            "auth": list(AUTH_LEVELS),
            "gate_meaning": {
                "none": "no elevation beyond authentication (see 'auth')",
                "step-up": "requires a require_step_up elevation: a "
                "time-bounded session grant, true loopback, or "
                "the delegated X-PW-StepUp header (only with "
                "X-PW-Proxy-StepUp-Secret matching "
                "PW_PROXY_STEPUP_SECRET)",
                "proposal": "requires an approved proposal from the "
                "propose → approve → act lifecycle",
            },
        },
        "endpoints": endpoints,
        "uncurated": uncurated,
        "coverage": {
            "curated": len(endpoints),
            "curated_present": sum(1 for e in endpoints if e["present"]),
            "uncurated": len(uncurated),
            "complete": not uncurated and not missing,
        },
        # Visible, named, never silently normalized. See module docstring.
        "writes_without_elevation": sorted(set(writes_without_elevation)),
        "curated_but_not_registered": missing,
    }
