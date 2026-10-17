"""Rooms — the main app renders other small backends (contract: room/0).

Worlds shows rooms; it never copies their code. A *room* is any service
that serves the five ``/room`` endpoints defined by the canonical Room
contract (``room/0``). This module is the front-door half: it learns
each room's address from the operator's environment, reads the
read-only endpoints (``GET /room``, ``GET /room/cards`` and
``GET /room/needs-you``) concurrently, and reports a row per
room. It owns no room's code
and adds no new listening port to Worlds — rooms are reached outbound,
same-origin behind the estate's own auth proxy in production.

Configuration (read at request time, never written anywhere):

* ``PW_ROOMS`` — a comma list of ``id=baseURL`` entries, e.g.
  ``studio=http://127.0.0.1:8940,workshop=https://127.0.0.1:8961``.
* ``PW_ROOM_<ID>_TOKEN_ENV`` — the **name** of the env var that holds
  that room's bearer token (same indirection as
  ``providers/project_home.py``'s ``PW_PH_TOKEN_ENV``). The token value
  is never logged and never appears in a returned field.
* ``PW_ROOM_<ID>_OWNER_TOKEN_ENV`` — the **name** of the env var that
  holds that room's *owner* token, a second, stronger secret some
  ``room/0`` rooms require (in addition to the bearer token above) on a
  write action, as ``X-Worlds-Owner-Token``. Same indirection as
  ``*_TOKEN_ENV``; optional, and most rooms configure none. See
  :data:`OWNER_HEADER`.
* ``PW_ROOM_<ID>_INSECURE_TLS=1`` — accept a self-signed certificate on
  a LAN room's HTTPS address.

Runtime room list (Gap 1 / ROOM clause 15): when
``PW_ROOMS_REGISTRY_URL`` names Project Home's ``GET
/api/rooms/registry``, Worlds reads its room list from that registry at
snapshot time instead of static env — adding or removing a room takes
effect on the next refresh, with no restart. The registry payload is
cached 60 s; a bearer token is read from the env var named by
``PW_ROOMS_REGISTRY_TOKEN_ENV`` (same indirection, never a value in a
returned field), and ``PW_ROOMS_REGISTRY_INSECURE_TLS=1`` accepts a
self-signed registry certificate. On a successful fetch the enabled
rooms are used and persisted as last-known-good (``rooms-registry.json``
under the data dir, the same atomic entry point as ``rooms-state.json``); on a
fetch failure the last-known-good is served and the problem is surfaced
 in the snapshot's registry report. Only when neither a
successful registry read nor a last-known-good exists does the module
fall back to ``PW_ROOMS`` — today's behaviour, unchanged.

Error handling: this module never raises out of :meth:`RoomsService
.snapshot`. A room that cannot be reached, times out, answers malformed
JSON, or speaks an unsupported contract value is reported as such —
never ``healthy``. ``unknown`` is not ``healthy`` and it is not failed;
an unreachable room renders as ``unreachable`` with its last-seen time,
and a room whose contract this main app does not support renders as
``incompatible`` with the reason — its cards and needs are never
counted.

A registry entry may also name an optional ``public_url``: a
browser-reachable ``http(s)`` address (no userinfo) for the room. It
rides each row as ``public_url`` and is a ``null`` when absent
or invalid; consumers then fall back to ``base_url``. The entry itself
is never dropped for a bad ``public_url``.

A registry entry may also opt in to **per-person forwarding** with
``forward_principal: true`` (default false; anything but JSON ``true``
is false, and env-configured ``PW_ROOMS`` never forwards). For such a
room, Worlds sends ``X-Worlds-Principal: <principal id>`` on every
request to it (``GET /room``, ``/room/cards``, ``/room/needs-you``, and
``POST /room/actions/{id}``) **in addition to** that room's own
bearer token — never instead of it. The token proves Worlds may read the
room; the principal header tells the room *who is asking* so it can
answer for that person. If the room has no token configured the header
is not sent at all (an unauthenticated identity claim is meaningless)
and the room is treated as non-forwarding. The principal id is the
caller's Worlds principal id, validated against the same safe-id rule
``identity.principal_scoped_path`` uses; an invalid id is never sent.
An action call is the one exception to the opt-in: an action is always
someone's, so :meth:`RoomsService.perform_action` sends
``X-Worlds-Principal`` whenever the room has a token, whether or not the
room opted in to read forwarding. The human's session token /
``PW_API_TOKEN`` is never sent to a room — only the room's own token is.

A forwarding room's health is still estate-wide (a room that is down is
down for everyone), but its cards and needs are per person:
:meth:`RoomsService.snapshot_for_principal` serves the shared 15 s
snapshot for non-forwarding rooms and, for forwarding rooms, a
per-principal fetch cached against the same 15 s TTL — keyed by room id +
principal id, bounded to :data:`MAX_FORWARD_PRINCIPALS` principals with
the oldest evicted. Nothing one principal's forwarded fetch returned can
appear in another principal's response. A caller with no request
principal (a background job, the digest) never forwards: it gets the
room's own default, non-personal view.

:meth:`RoomsService.secrets_overview` is the Worlds side of the
read-only Secrets board: it finds the room named ``workshop`` and reads
its ``GET /api/secrets/summary`` with that room's token/TLS policy (3 s
timeout, cached 60 s). It reports names and health only — never a value
— and any failure is an ``unknown`` station with a plain-words
detail, never an invented key and never a raised exception.

``last_seen``/``last_status`` persist to ``rooms-state.json`` under the
data dir (rule 12's "persists last-seen timestamps"), so an unreachable
room still reports its real last-seen time after a restart; ``null``
means the room has truly never answered. Per-person visit state lives
elsewhere (``rooms_visits.py``) — this module owns global estate health
only and never learns who is looking.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# The same safe-principal-id rule ``identity.principal_scoped_path`` uses,
# so a forwarded principal id can never be a path/header injection. A room
# write needs the ``approve`` permission (roles.can) — one shared rule.
from .identity import _SAFE_PRINCIPAL_ID
from .roles import can

_logger = logging.getLogger("personal_world.rooms")

#: Env var holding the room list (``id=baseURL`` comma-separated).
ROOMS_ENV = "PW_ROOMS"

#: Registry env (Gap 1): the full URL of Project Home's
#: ``GET /api/rooms/registry``, the env var NAME holding the registry
#: bearer token (same indirection as ``PW_ROOM_<ID>_TOKEN_ENV``), and an
#: optional "1" to accept a self-signed registry certificate.
REGISTRY_URL_ENV = "PW_ROOMS_REGISTRY_URL"
REGISTRY_TOKEN_ENV_ENV = "PW_ROOMS_REGISTRY_TOKEN_ENV"  # nosec B105  # the NAME of the env var holding the token
REGISTRY_INSECURE_TLS_ENV = "PW_ROOMS_REGISTRY_INSECURE_TLS"

#: Registry HTTP cache (rule: 60 s) and hard timeout (rule: 3 s).
REGISTRY_CACHE_TTL_SECONDS = 60.0
REGISTRY_TIMEOUT_SECONDS = 3.0

#: Per-room env var suffixes. ``<ID>`` is the room id upper-cased with
#: every non-alphanumeric character folded to ``_`` (so ``my-room``
#: reads ``PW_ROOM_MY_ROOM_TOKEN_ENV``). ``*_TOKEN_ENV`` holds the
#: *name* of the env var carrying the token; ``*_OWNER_TOKEN_ENV`` holds
#: the *name* of the env var carrying the room's owner token (same
#: indirection, optional); ``*_INSECURE_TLS`` is "1" to accept a
#: self-signed LAN certificate.
TOKEN_ENV_SUFFIX = "_TOKEN_ENV"  # nosec B105  # an env var NAME suffix, not a credential
OWNER_TOKEN_ENV_SUFFIX = "_OWNER_TOKEN_ENV"  # nosec B105  # an env var NAME suffix, not a credential
INSECURE_TLS_SUFFIX = "_INSECURE_TLS"

#: Paths stay exactly these — there is no per-version path (rule 1).
ROOM_PATH = "/room"
CARDS_PATH = "/room/cards"
NEEDS_YOU_PATH = "/room/needs-you"
ACTIONS_PATH = "/room/actions"

#: Passing a room/0 action through to the room. The caller names one
#: action; Worlds reads the room's own action list (cached 60 s per
#: room, never per person), enforces the ``approve`` permission for
#: writes, requires an idempotency key, and forwards the call to the
#: room's ``POST /room/actions/{id}``. The room's own receipt comes back.
ACTION_TIMEOUT_SECONDS = 10.0
ACTIONS_CACHE_TTL_SECONDS = 60.0

#: The request header a caller must present so a retry cannot double-act.
IDEMPOTENCY_HEADER = "Idempotency-Key"
IDEMPOTENCY_VALUE_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

#: An action id: lower-case letter/digit start, then letters, digits and
#: hyphens, at most 64 chars (the shared interface's action-id rule).
_VALID_ACTION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

#: Read-only views a room may offer (``GET /room/views/{name}[/{item}]``),
#: e.g. Hive Works' teams, projects, one project, crew.
VIEWS_PATH = "/room/views"
_VALID_VIEW_NAME = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_VALID_VIEW_ITEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_VIEW_BYTES = 512 * 1024
VIEW_TIMEOUT_SECONDS = 5.0
VIEW_CACHE_SECONDS = 15.0
#: Pictures a room may offer (``GET /room/art/{name}.webp``), e.g. Hive
#: Works' crew faces. WebP only; the browser can't send a room's token, so
#: Worlds passes them through.
ART_PATH = "/room/art"
_VALID_ART_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
MAX_ART_BYTES = 2 * 1024 * 1024
ART_CACHE_SECONDS = 3600.0
#: A room's library (Play-Nice ``library/0``), an optional ROOM extra.
STICKERS_PATH = "/room/views/stickers"
LIBRARY_PATH = "/room/library"
MAX_LIBRARY_BYTES = 1024 * 1024


def _is_library(doc: Any) -> bool:
    """The minimum shape of a ``library/0`` document Worlds relies on."""
    if not isinstance(doc, dict) or doc.get("contract") != "library/0":
        return False
    keeper = doc.get("keeper")
    if not isinstance(keeper, dict) or not isinstance(keeper.get("id"), str) or not isinstance(keeper.get("name"), str):
        return False
    if not isinstance(doc.get("shelves"), list) or not isinstance(doc.get("books"), list):
        return False
    for book in doc["books"]:
        if not isinstance(book, dict) or not isinstance(book.get("title"), str) or not isinstance(book.get("short"), str):
            return False
        pages = book.get("pages")
        if not isinstance(pages, list) or not pages or not all(
            isinstance(p, dict) and p.get("kind") in ("plain", "voice", "words", "technical")
            and isinstance(p.get("text"), str)
            for p in pages
        ):
            return False
    return True


#: Change pings from one room closer together than this fold into one.
PING_MIN_GAP_SECONDS = 2.0
#: Events a slow listener may queue before it starts missing pings.
LISTENER_QUEUE = 32

#: A forwarded action body is a JSON object at most this many bytes.
MAX_ACTION_BODY_BYTES = 16 * 1024

#: The five receipt fields. A room's answer is allow-listed to exactly
#: these — anything else it sends is dropped, never trusted through.
RECEIPT_FIELDS = ("action_id", "ok", "summary", "changed", "at")

#: The Secrets overview reads the room the shared interface fixes by id
#: (``workshop``), at its read-only summary path, with that room's own
#: token/TLS policy. A 3 s timeout and a 60 s cache match the other
#: front-door reads.
SECRETS_ROOM_ID = "workshop"
SECRETS_SUMMARY_PATH = "/api/secrets/summary"
SECRETS_TIMEOUT_SECONDS = 3.0
SECRETS_CACHE_TTL_SECONDS = 60.0

#: The interface version this consumer understands (rule 14). An entry
#: (registry) or descriptor contract outside this set is ``incompatible``
#: — never rendered, never healthy, and never guessed.
CONTRACT_VALUE = "room/0"
SUPPORTED_CONTRACTS = frozenset({CONTRACT_VALUE})

#: The four statuses a descriptor may declare (rule 2).
ROOM_STATUSES = frozenset({"healthy", "degraded", "unhealthy", "unknown"})

#: The card tones the contract names (rule 3). A tone outside this set is
#: treated as ``update`` by consumers — never as ``when_ready``.
CARD_TONES = frozenset({"good_news", "update", "when_ready"})

#: The front-door word for a room that did not answer (rule 12).
UNREACHABLE = "unreachable"

#: The front-door word for a room whose contract (registry entry or its
#: own descriptor) this consumer does not support — a distinct fact from
#: "unreachable": it answered, or was refused before it was loaded.
INCOMPATIBLE = "incompatible"

#: Hard timeout per outbound request — a dead room degrades, never hangs.
TIMEOUT_SECONDS = 2.0

#: How long one snapshot is served before the estate is re-checked.
CACHE_TTL_SECONDS = 15.0

#: The header that tells a forwarding room who is asking. It rides every
#: request to a room whose registry entry opted in (``forward_principal``)
#: AND that configured its own token, alongside that room's bearer token —
#: never instead of it, and never when the room has no token.
PRINCIPAL_HEADER = "X-Worlds-Principal"

#: The header that proves an action call to a room really comes from the
#: Worlds broker, not merely from anyone holding the room's ordinary
#: bearer token. Sent in addition to ``Authorization`` — never instead of
#: it — on a write action (``writes`` is not ``False``, the room's own
#: fail-closed rule) to a room that configured an owner token
#: (``PW_ROOM_<ID>_OWNER_TOKEN_ENV``). Generic and keyed only by the
#: action's own ``writes`` flag, not by room id or action id, so any
#: ``room/0`` room may opt in by configuring the env var — not only
#: hive-works, the first room to require it (``HW_ROOM_OWNER_TOKEN``,
#: 2026-09-28: ``X-Worlds-Principal`` is client-supplied and not
#: cryptographically bound to the caller, so it cannot gate owner-only
#: actions by itself). No owner token configured for a room means the
#: header is never sent to it.
OWNER_HEADER = "X-Worlds-Owner-Token"

#: At most this many principals have their forwarded cards/needs cached;
#: the oldest principal's entries are evicted past the cap.
MAX_FORWARD_PRINCIPALS = 64

#: Where per-room health (last-seen / last-declared-status) is persisted
#: under the data dir. Plain JSON on the same atomic-write entry point every
#: other Worlds state file uses: rooms are global estate health, not
#: per-person state, so this is deliberately one shared file (not a
#: per-principal scoped kind).
STATE_FILENAME = "rooms-state.json"

#: Last-known-good registry payload (rooms + updated_at) persisted under
#: the data dir on the same atomic entry point — so a registry outage still
#: serves the estate the registry last named.
REGISTRY_STATE_FILENAME = "rooms-registry.json"

_ID_UNSAFE = re.compile(r"[^A-Za-z0-9]")

#: A registry room id: lower-case letter/digit start, then letters,
#: digits and hyphens (the shared interface's ``^[a-z0-9][a-z0-9-]*$``).
_VALID_ROOM_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


#: Registry token_env must name a room token, e.g. PW_ROOM_WORKSHOP_TOKEN.
_ROOM_TOKEN_ENV_RE = re.compile(r"^PW_ROOM_[A-Z0-9_]+_TOKEN$")

#: Registry owner_token_env must name a room owner token, e.g.
#: PW_ROOM_HIVE_WORKS_OWNER_TOKEN. Same shape rule as the bearer token,
#: so a registry entry can never redirect an unrelated secret here.
_ROOM_OWNER_TOKEN_ENV_RE = re.compile(r"^PW_ROOM_[A-Z0-9_]+_OWNER_TOKEN$")

def env_name(room_id: str, suffix: str) -> str:
    """``("studio", "_TOKEN_ENV") -> "PW_ROOM_STUDIO_TOKEN_ENV"``.

    Room ids are operator-chosen; the env mapping is deterministic and
    reversible enough for a human to read, so no lookup table is needed.
    """
    folded = _ID_UNSAFE.sub("_", room_id).upper()
    return f"PW_ROOM_{folded}{suffix}"


def _valid_absolute_http_url(url: str) -> bool:
    try:
        parts = httpx.URL(url)
    except (httpx.InvalidURL, ValueError):
        return False
    return parts.scheme in ("http", "https") and bool(parts.host)


def _valid_public_url(url: str) -> bool:
    """A browser-reachable ``public_url``: absolute http(s), no userinfo.

    Stricter than :func:`_valid_absolute_http_url`: a public URL is shown
    to browsers, so credentials embedded in it (``https://user:pass@…``)
    are refused. An invalid value never drops the room — the entry is
    kept with ``public_url`` null, and consumers fall back to
    ``base_url``.
    """
    if not _valid_absolute_http_url(url):
        return False
    try:
        parts = httpx.URL(url)
    except (httpx.InvalidURL, ValueError):
        return False
    return not parts.userinfo


@dataclass(frozen=True)
class RoomConfig:
    """One configured room, resolved from the environment or a registry.

    ``invalid_reason`` is set when the entry could not be used as
    configured (a missing/relative URL). Such a room is reported as
    unreachable with that reason rather than silently dropped.
    ``contract`` is the interface version the source claimed (``room/0``
    for env entries); a value outside :data:`SUPPORTED_CONTRACTS` makes
    the row ``incompatible``. ``token_env`` is the **name** of the env
    var the token was read from (or ``None``) — carried so a
    last-known-good can re-read the token on a later boot; the token
    value itself is never persisted or returned. ``owner_token`` /
    ``owner_token_env`` are the same indirection for the room's optional
    *owner* token: a second, stronger secret some rooms require (in
    addition to the bearer token) on a write action, sent as
    :data:`OWNER_HEADER`. ``None`` when the room configured none (most
    rooms today). ``public_url`` is the
    browser-reachable address a registry entry may name (http(s), no
    userinfo); it is ``None`` when absent or invalid, and consumers then
    fall back to ``base_url``. ``forward_principal`` is a registry
    opt-in: when true the room is told who is asking (via
    ``X-Worlds-Principal``, alongside its token) and its cards/needs are
    served per person. It is false for env-configured rooms and for any
    registry value that is not JSON ``true``.
    """

    id: str
    base_url: str
    token: str | None = None
    insecure_tls: bool = False
    invalid_reason: str | None = None
    contract: str = CONTRACT_VALUE
    token_env: str | None = None
    owner_token: str | None = None
    owner_token_env: str | None = None
    public_url: str | None = None
    forward_principal: bool = False
    #: The human name a registry entry declared (or ``None`` for an env
    #: room, which names only an id). Carried so a failed action can say
    #: the room's real name; never required, never a status.
    name: str | None = None


def parse_rooms(env: dict | None = None) -> list[RoomConfig]:
    """Resolve the configured rooms from ``PW_ROOMS`` and its per-room vars.

    Duplicate ids keep the first entry. An entry with no id is skipped
    (there is nothing to address it by); an entry with an id but an
    unusable URL is kept, so the main app can report it.
    """
    env = os.environ if env is None else env
    raw = (env.get(ROOMS_ENV) or "").strip()
    if not raw:
        return []

    rooms: list[RoomConfig] = []
    seen: set[str] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        room_id, sep, base = entry.partition("=")
        room_id = room_id.strip()
        base = base.strip()
        if not room_id or room_id in seen:
            continue
        seen.add(room_id)

        token_env_name = (env.get(env_name(room_id, TOKEN_ENV_SUFFIX)) or "").strip()
        token = (env.get(token_env_name) or "").strip() if token_env_name else ""
        owner_token_env_name = (
            env.get(env_name(room_id, OWNER_TOKEN_ENV_SUFFIX)) or ""
        ).strip()
        owner_token = (
            (env.get(owner_token_env_name) or "").strip()
            if owner_token_env_name
            else ""
        )
        insecure = (
            env.get(env_name(room_id, INSECURE_TLS_SUFFIX)) or ""
        ).strip() == "1"

        reason: str | None = None
        if not sep or not base:
            reason = "missing base URL"
        elif not _valid_absolute_http_url(base):
            reason = "base URL must be an absolute http(s) address"

        rooms.append(
            RoomConfig(
                id=room_id,
                base_url=base,
                token=token or None,
                insecure_tls=insecure,
                invalid_reason=reason,
                token_env=token_env_name or None,
                owner_token=owner_token or None,
                owner_token_env=owner_token_env_name or None,
            )
        )
    return rooms


def _parse_registry_entries(
    entries: Any, env: dict
) -> tuple[list[RoomConfig], int]:
    """``(configs, dropped)`` from a registry ``rooms`` list.

    Malformed entries are dropped, never guessed: a missing/bad id, a
    non-http(s) ``base_url``, a non-string ``contract``, or a non-string
    ``token_env``. An ``enabled: false`` entry is skipped (the registry
    returns it; consumers do not load it) and is not counted as dropped.
    A ``contract`` outside :data:`SUPPORTED_CONTRACTS` is kept as an
    ``incompatible`` row so the person can see why it is not loaded.
    ``forward_principal`` rides through only as strict JSON ``true``.
    """
    if not isinstance(entries, list):
        return [], 0
    configs: list[RoomConfig] = []
    dropped = 0
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            dropped += 1
            continue
        room_id = entry.get("id")
        if (
            not isinstance(room_id, str)
            or not _VALID_ROOM_ID.match(room_id)
            or room_id in seen
        ):
            dropped += 1
            continue
        if entry.get("enabled") is False:
            continue  # returned by the registry, deliberately not loaded
        base = entry.get("base_url")
        if not isinstance(base, str) or not _valid_absolute_http_url(base):
            dropped += 1
            continue
        contract = entry.get("contract")
        if not isinstance(contract, str) or not contract:
            dropped += 1
            continue
        token_env_name = entry.get("token_env")
        if token_env_name is not None and not isinstance(token_env_name, str):
            dropped += 1
            continue
        token_env_name = (token_env_name or "").strip()
        # The registry names WHICH env var holds a room's token, and that token
        # is then sent to the room's base_url. Only room-token names are
        # honoured, so an entry can never make Worlds send PW_API_TOKEN or a
        # provider key to an arbitrary URL; anything else is ignored.
        if token_env_name and not _ROOM_TOKEN_ENV_RE.match(token_env_name):
            token_env_name = ""  # nosec B105  # an empty rejected value, not a credential
        token = (env.get(token_env_name) or "").strip() if token_env_name else ""
        # Same indirection, same allow-list rule, for the optional owner
        # token: only an owner-token-shaped env var NAME is honoured, so a
        # registry entry can never redirect PW_API_TOKEN or a provider key
        # here either.
        owner_token_env_name = entry.get("owner_token_env")
        if owner_token_env_name is not None and not isinstance(owner_token_env_name, str):
            dropped += 1
            continue
        owner_token_env_name = (owner_token_env_name or "").strip()
        if owner_token_env_name and not _ROOM_OWNER_TOKEN_ENV_RE.match(owner_token_env_name):
            owner_token_env_name = ""  # nosec B105  # an empty rejected value, not a credential
        owner_token = (
            (env.get(owner_token_env_name) or "").strip()
            if owner_token_env_name
            else ""
        )
        # A public_url is optional and never drops the entry: a missing,
        # non-string, non-http(s) or userinfo-bearing value is simply not
        # trusted, and consumers fall back to base_url.
        public_url = entry.get("public_url")
        if public_url is not None and (
            not isinstance(public_url, str) or not _valid_public_url(public_url)
        ):
            public_url = None
        # A display name is optional and never drops the entry; a
        # missing/non-string/empty value is None (consumers fall
        # back to the id).
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            name = None
        seen.add(room_id)
        configs.append(
            RoomConfig(
                id=room_id,
                base_url=base,
                token=token or None,
                insecure_tls=entry.get("insecure_tls") is True,
                contract=contract,
                token_env=token_env_name or None,
                owner_token=owner_token or None,
                owner_token_env=owner_token_env_name or None,
                public_url=public_url or None,
                # Opt-in per-person forwarding: strictly JSON true. Any
                # other value (false, "true", 1, missing) is false.
                forward_principal=entry.get("forward_principal") is True,
                name=name,
            )
        )
    return configs, dropped


def _parse_registry_payload(
    payload: Any, env: dict
) -> tuple[list[RoomConfig], int] | None:
    """``(configs, dropped)`` from a registry payload, or ``None`` when the
    payload as a whole is malformed (not an object, or no ``rooms`` list) —
    the caller treats that as a failed fetch, not an empty registry."""
    if not isinstance(payload, dict):
        return None
    rooms = payload.get("rooms")
    if not isinstance(rooms, list):
        return None
    return _parse_registry_entries(rooms, env)


def _lkg_entries(configs: list[RoomConfig]) -> list[dict]:
    """The sanitized, persistable last-known-good entries: only the known
    registry fields, and never a token value (only its env var NAME)."""
    return [
        {
            "id": c.id,
            "base_url": c.base_url,
            "contract": c.contract,
            "token_env": c.token_env,
            "owner_token_env": c.owner_token_env,
            "insecure_tls": c.insecure_tls,
            "public_url": c.public_url,
            # Persisted so a forwarding room's opt-in survives a registry
            # outage via last-known-good.
            "forward_principal": c.forward_principal,
            # The display name a failed action quotes back to the person.
            "name": c.name,
        }
        for c in configs
    ]


def _reason(exc: BaseException) -> str:
    """A short failure class only — never a URL, token, or payload."""
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        return "connect error"
    if isinstance(exc, httpx.HTTPError):
        return f"http error ({type(exc).__name__})"
    return f"request failed ({type(exc).__name__})"


def _registry_report(
    source: str,
    status: str,
    checked_at: str | None,
    error: str | None,
    updated_at: str | None,
    dropped: int,
) -> dict[str, Any]:
    """The registry half of the snapshot, stated plainly.

    ``source`` is where the room list came from (``registry`` |
    ``last_known_good`` | ``env``); ``status`` is the registry read
    itself (``ok`` | ``unreachable`` | ``not_configured``); ``error`` is a
    short failure class only — never a URL, token, or payload.
    """
    return {
        "source": source,
        "status": status,
        "checked_at": checked_at,
        "error": error,
        "updated_at": updated_at,
        "dropped": dropped,
    }


#: The closed station statuses the Secrets summary may declare. Anything
#: else is reported as ``unknown`` — never guessed healthy.
_STATION_STATUSES = frozenset({"ok", "unreachable", "not_configured"})

#: The fields copied off a summary's ``requests`` / ``recent_ops`` rows.
#: Built by allow-list so a station that (wrongly) includes a secret
#: value can never leak it into the board.
_REQUEST_KEYS = ("id", "key_path", "reason", "requested_at", "link")
_OP_KEYS = ("key_path", "state", "deploy_state", "actor", "created_at")


def _empty_secrets_summary() -> dict[str, Any]:
    """The empty summary — the shape every overview response keeps."""
    return {
        "station": {"configured": False, "status": "not_configured", "detail": None},
        "namespaces": [],
        "key_count": 0,
        "bundle_last_change": None,
        "requests": [],
        "recent_ops": [],
        "links": {"trusted_form": "/secrets"},
    }


def _open_secrets_url(config: RoomConfig, trusted_form: str) -> str | None:
    """``(public_url or base_url) + links.trusted_form`` for the board.

    ``public_url`` is preferred (browser-reachable); ``base_url`` is the
    documented fallback. ``trusted_form`` must be a same-origin path, or
    the default ``/secrets`` is used — never a station-supplied absolute
    URL.
    """
    if not isinstance(trusted_form, str) or not trusted_form.startswith("/"):
        trusted_form = "/secrets"
    base = (config.public_url or config.base_url).rstrip("/")
    return base + trusted_form


def _unknown_secrets_overview(
    detail: str, config: RoomConfig | None = None
) -> dict[str, Any]:
    """The "cannot read it" overview: unknown station, empty rest.

    Never invents a namespace, key, request or op. ``room_id`` is always
    stated; ``open_url`` is stated only when a usable room address is
    known (``None`` otherwise), so the board can link when it can.
    """
    data = _empty_secrets_summary()
    data["station"] = {"configured": False, "status": "unknown", "detail": detail}
    data["room_id"] = SECRETS_ROOM_ID
    data["open_url"] = (
        _open_secrets_url(config, data["links"]["trusted_form"])
        if config is not None
        else None
    )
    return data


def _sanitize_secrets_summary(
    payload: dict, config: RoomConfig
) -> dict[str, Any]:
    """The station summary in the known shape, and nothing else.

    Built from an allow-list of known fields, so a station that (wrongly)
    includes a ``value`` key can never leak it, and consumers can rely on
    the shape. Namespace and key names come only from the station; none
    are invented here.
    """
    data = _empty_secrets_summary()

    station = payload.get("station")
    if isinstance(station, dict):
        status = station.get("status")
        detail = station.get("detail")
        data["station"] = {
            "configured": station.get("configured") is True,
            "status": status if status in _STATION_STATUSES else "unknown",
            "detail": detail if isinstance(detail, str) else None,
        }

    namespaces = payload.get("namespaces")
    if isinstance(namespaces, list):
        cleaned: list[dict[str, Any]] = []
        for ns in namespaces:
            if not isinstance(ns, dict) or not isinstance(ns.get("name"), str):
                continue
            keys = ns.get("keys")
            cleaned.append(
                {
                    "name": ns["name"],
                    "keys": (
                        [k for k in keys if isinstance(k, str)]
                        if isinstance(keys, list)
                        else []
                    ),
                }
            )
        data["namespaces"] = cleaned

    key_count = payload.get("key_count")
    if isinstance(key_count, int) and not isinstance(key_count, bool) and key_count >= 0:
        data["key_count"] = key_count

    change = payload.get("bundle_last_change")
    if isinstance(change, str):
        data["bundle_last_change"] = change

    requests = payload.get("requests")
    if isinstance(requests, list):
        data["requests"] = [
            {key: row.get(key) for key in _REQUEST_KEYS}
            for row in requests
            if isinstance(row, dict)
        ]

    recent_ops = payload.get("recent_ops")
    if isinstance(recent_ops, list):
        data["recent_ops"] = [
            {key: row.get(key) for key in _OP_KEYS}
            for row in recent_ops
            if isinstance(row, dict)
        ]

    links = payload.get("links")
    if isinstance(links, dict):
        trusted = links.get("trusted_form")
        if isinstance(trusted, str) and trusted.startswith("/"):
            data["links"] = {"trusted_form": trusted}

    data["room_id"] = SECRETS_ROOM_ID
    data["open_url"] = _open_secrets_url(config, data["links"]["trusted_form"])
    return data


def _safe_principal_id(raw: Any) -> str | None:
    """A principal id safe to put in a header, or ``None``.

    Uses the exact safe-id rule ``identity.principal_scoped_path`` uses,
    so an id that could never name a scoped path is also never forwarded
    to a room.
    """
    if not isinstance(raw, str) or not _SAFE_PRINCIPAL_ID.match(raw):
        return None
    return raw


def _receipt(
    action_id: str,
    ok: bool,
    summary: str,
    changed: Any = None,
    at: Any = None,
) -> dict[str, Any]:
    """One receipt in the known shape and nothing else.

    The five allow-listed fields (:data:`RECEIPT_FIELDS`): ``action_id``,
    ``ok``, ``summary``, ``changed`` (a list, or ``[]``), and ``at`` (an
    ISO timestamp, or now). Built here so every receipt — local refusal or
    a room's own answer — has exactly one shape.
    """
    return {
        "action_id": action_id,
        "ok": bool(ok),
        "summary": summary,
        "changed": changed if isinstance(changed, list) else [],
        "at": at if isinstance(at, str) and at else _iso_now(),
    }


def _sanitize_receipt(payload: Any, action_id: str) -> dict[str, Any] | None:
    """A room's answer as a receipt, or ``None`` when it is not one.

    Receipt-shaped means a JSON object with a boolean ``ok``. Everything
    else is dropped: ``action_id`` falls back to the one we asked for,
    ``summary`` to an empty string, ``changed`` to ``[]``, ``at`` to now.
    Any other key the room sent is discarded, never passed through.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
        return None
    return _receipt(
        action_id=(
            payload["action_id"]
            if isinstance(payload.get("action_id"), str)
            else action_id
        ),
        ok=payload["ok"],
        summary=payload.get("summary")
        if isinstance(payload.get("summary"), str)
        else "",
        changed=payload.get("changed"),
        at=payload.get("at"),
    )


def _is_json_object(raw: bytes) -> bool:
    """True when a forwarded action body is JSON and an object.

    The *contents* are the room's business (validation is its job); this
    only keeps the envelope shape .
    """
    try:
        return isinstance(json.loads(raw), dict)
    except (ValueError, UnicodeDecodeError):
        return False


def _parse_room_actions(payload: Any) -> list[dict[str, Any]] | None:
    """``[action, …]`` from a room's ``GET /room/actions`` answer, or
    ``None`` when the answer cannot be read.

    Accepts either a bare list or an object wrapping ``actions``; malformed
    rows are dropped (never guessed). ``None`` means the room did not give
    a usable list — the caller then fails closed (unknown action).
    """
    if isinstance(payload, dict):
        payload = payload.get("actions")
    if not isinstance(payload, list):
        return None
    return [row for row in payload if isinstance(row, dict)]


_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
MAX_FIELDS = 6
MAX_OPTIONS = 12


def _clip(value: Any, limit: int) -> str:
    return str(value).strip()[:limit]


def _action_form(schema: Any) -> tuple[list[dict[str, Any]] | None, bool]:
    """``(fields, need_bound)`` from a room action's ``input_schema``.

    ``fields`` is a small, checked form the UI can draw — text boxes,
    one-of choices and pick-several choices — or ``None`` when the schema
    has something the UI can't draw (then the action is a plain button).
    ``need_bound`` is True when the action takes a ``need``: it answers
    one need and is offered on that need, never as a room action.
    """
    if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict):
        return None, False
    props = schema["properties"]
    if "need" in props:
        return None, True
    required = {r for r in schema.get("required") or [] if isinstance(r, str)}
    fields: list[dict[str, Any]] = []
    for name, spec in props.items():
        if not _FIELD_NAME.match(str(name)) or not isinstance(spec, dict) or len(fields) >= MAX_FIELDS:
            return None, False
        label = _clip(spec.get("title") or name.replace("_", " ").capitalize(), 60)
        kind = spec.get("type")
        items = spec.get("items") if kind == "array" else spec
        enum = items.get("enum") if isinstance(items, dict) else None
        if enum is not None:
            if not isinstance(enum, list) or not 0 < len(enum) <= MAX_OPTIONS or not all(
                isinstance(v, str) and 0 < len(v) <= 40 for v in enum
            ):
                return None, False
            names = spec.get("enumNames")
            if not (isinstance(names, list) and len(names) == len(enum)):
                names = enum
            field: dict[str, Any] = {
                "name": name,
                "kind": "choices" if kind == "array" else "choice",
                "label": label,
                "required": name in required,
                "options": [{"value": v, "label": _clip(n, 40)} for v, n in zip(enum, names, strict=True)],
            }
            if kind == "array":
                most = spec.get("maxItems")
                field["max"] = most if isinstance(most, int) and 0 < most <= len(enum) else len(enum)
        elif kind == "string":
            most = spec.get("maxLength")
            field = {
                "name": name,
                "kind": "text",
                "label": label,
                "required": name in required,
                "max_length": most if isinstance(most, int) and 0 < most <= 2000 else 500,
            }
        else:
            return None, False
        fields.append(field)
    return (fields or None), False


def _merge_personal(
    shared: dict[str, Any], forwarded: dict[str, Any]
) -> dict[str, Any]:
    """One caller's row for a forwarding room.

    Health is estate-wide (``reachable``, ``status``, ``last_seen``,
    ``last_status``, ``checked_at``), so it comes from the shared row —
    a room that is down is down for everyone. Only the person's ``cards``
    and ``needs_you`` come from their own forwarded fetch. If that fetch
    itself failed, its error is stated (empty cards/needs, never the
    default view presented as theirs) while the room's shared health
    stands.
    """
    merged = dict(shared)
    merged["cards"] = forwarded["cards"]
    merged["needs_you"] = forwarded["needs_you"]
    if not forwarded["reachable"]:
        merged["error"] = forwarded["error"]
    return merged


class RoomsService:
    """Reads every configured room; caches one snapshot for 15 s.

    :meth:`snapshot` is the estate-wide view (no principal): forwarding
    rooms answer it with their own default, non-personal view. A request
    handler calls :meth:`snapshot_for_principal` instead, which layers
    the caller's own forwarded cards/needs over the shared rows for the
    rooms that opted in.

    ``last_seen``/``last_status`` are persisted per room id through
    ``state_path`` (a JSON file on the data dir) so an unreachable room
    still reports when it was last reached — across a restart, not just
    for the process lifetime. With no ``state_path`` the service keeps
    them in memory only (tests, and any embedding that wants no disk).

    The room list itself is resolved per snapshot: from a configured
    registry (``PW_ROOMS_REGISTRY_URL``, cached 60 s) with last-known-good
    persisted through ``registry_state_path``, falling back to
    ``PW_ROOMS`` only when the registry yields nothing. Inject
    ``transport`` (an ``httpx`` transport) and ``clock`` in tests;
    production uses the network and ``time.monotonic``.
    """

    def __init__(
        self,
        transport=None,
        clock=None,
        state_path=None,
        registry_state_path=None,
    ) -> None:
        self._transport = transport
        self._clock = clock or time.monotonic
        self._cache: list[dict[str, Any]] | None = None
        self._cache_at: float = float("-inf")
        # Per-person forwarded rows for forwarding rooms, keyed by
        # (room id, principal id) and cached against the same 15 s TTL.
        # Insertion order is refresh order, so the oldest principal is
        # evicted first once the cap is passed.
        self._principal_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
        self._state_path: Path | None = (
            Path(state_path) if state_path is not None else None
        )
        self._last_seen: dict[str, str] = {}
        self._last_status: dict[str, str] = {}
        self._dirty = False
        self._load_persisted()

        # Registry state (Gap 1): the last-known-good payload, the cached
        # resolution (60 s), and the report served as a sibling of
        # ``data`` in GET /api/rooms.
        self._registry_state_path: Path | None = (
            Path(registry_state_path) if registry_state_path is not None else None
        )
        self._lkg: dict[str, Any] | None = None
        self._resolved: tuple[list[RoomConfig], dict[str, Any]] | None = None
        self._resolved_at: float = float("-inf")
        self._last_configs: list[RoomConfig] | None = None
        self._registry_report: dict[str, Any] = _registry_report(
            "env", "not_configured", None, None, None, 0
        )
        self._load_registry_lkg()

        # The Secrets overview (Worlds side) is one outbound read of the
        # ``workshop`` room, cached 60 s like the registry.
        # Live updates: open screens subscribe; a room's "changed" ping or
        # a successful action publishes {room, at}. Room ids only, never
        # content, so any signed-in listener may hear them.
        self._listeners: set[asyncio.Queue] = set()
        self._last_ping: dict[str, float] = {}
        self._views_cache: dict[tuple[str, str, str], tuple[float, int, Any]] = {}
        self._secrets_cache: dict[str, Any] | None = None
        self._secrets_cache_at: float = float("-inf")

        # Each room's own ``GET /room/actions`` list, cached per room (NOT
        # per person) for 60 s. ``None`` is a "could not read the
        # list" — the action gate then fails closed. A failed read is
        # cached too, so one dead room is not hammered by every caller.
        self._actions_cache: dict[
            str, tuple[float, list[dict[str, Any]] | None]
        ] = {}

    # -- app wiring ------------------------------------------------------

    def set_state_path(self, state_path) -> None:
        """Point the service at a persistent state file (app wiring).

        Idempotent; re-reads the file so a restart restores the estate's
        last-seen times rather than claiming "never reached".
        """
        self._state_path = Path(state_path) if state_path is not None else None
        self._load_persisted()

    def set_registry_state_path(self, registry_state_path) -> None:
        """Point the service at the last-known-good registry file.

        Idempotent; re-reads it so a restart can serve the registry's
        last room list while the registry is unreachable.
        """
        self._registry_state_path = (
            Path(registry_state_path) if registry_state_path is not None else None
        )
        self._load_registry_lkg()

    def registry_report(self) -> dict[str, Any]:
        """The registry state behind the last snapshot."""
        return dict(self._registry_report)

    def known_ids(self) -> list[str]:
        """The ids of the last resolved room list (registry or env).

        The synchronous entry point the api's room-id validators use; before any
        snapshot it falls back to the configured ``PW_ROOMS``.
        """
        if self._last_configs is not None:
            return [c.id for c in self._last_configs]
        return [c.id for c in parse_rooms()]

    def _load_persisted(self) -> None:
        """Best-effort restore. A missing/corrupt file is an empty state, never a fabricated last-seen."""
        self._last_seen = {}
        self._last_status = {}
        if self._state_path is None or not self._state_path.exists():
            return
        try:
            stored = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        rooms = stored.get("rooms") if isinstance(stored, dict) else None
        if not isinstance(rooms, dict):
            return
        for room_id, entry in rooms.items():
            if not isinstance(room_id, str) or not isinstance(entry, dict):
                continue
            seen = entry.get("last_seen")
            status = entry.get("last_status")
            if isinstance(seen, str) and seen:
                self._last_seen[room_id] = seen
            if isinstance(status, str) and status in ROOM_STATUSES:
                self._last_status[room_id] = status

    def _persist(self) -> None:
        """Persist room health atomically; a write failure is logged and
        never breaks a snapshot (remote loss must not break Worlds)."""
        if self._state_path is None or not self._dirty:
            return
        payload = {
            "rooms": {
                room_id: {
                    "last_seen": self._last_seen.get(room_id),
                    "last_status": self._last_status.get(room_id),
                }
                for room_id in sorted(set(self._last_seen) | set(self._last_status))
            }
        }
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.chmod(0o600)
            os.replace(tmp, self._state_path)  # atomic: no half state
            self._dirty = False
        except OSError as exc:
            _logger.warning("rooms state persist failed: %s", exc)

    # -- registry (Gap 1) ------------------------------------------------

    def _load_registry_lkg(self) -> None:
        """Best-effort restore of the last-known-good registry payload.

        A missing/corrupt file is a "no last-known-good", never a
        fabricated room list. Only the sanitized fields are kept.
        """
        self._lkg = None
        if self._registry_state_path is None or not self._registry_state_path.exists():
            return
        try:
            stored = json.loads(self._registry_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(stored, dict) or not isinstance(stored.get("rooms"), list):
            return
        updated_at = stored.get("updated_at")
        self._lkg = {
            "updated_at": updated_at if isinstance(updated_at, str) else None,
            "fetched_at": (
                stored.get("fetched_at")
                if isinstance(stored.get("fetched_at"), str)
                else None
            ),
            "rooms": stored["rooms"],
        }

    def _persist_registry_lkg(self) -> None:
        """Persist the last-known-good atomically (0600); a write failure
        is logged and never breaks a snapshot."""
        if self._registry_state_path is None or self._lkg is None:
            return
        try:
            self._registry_state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._registry_state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._lkg), encoding="utf-8")
            tmp.chmod(0o600)
            os.replace(tmp, self._registry_state_path)  # atomic: no half state
        except OSError as exc:
            _logger.warning("rooms registry persist failed: %s", exc)

    def _configs_from_lkg(self, env: dict) -> tuple[list[RoomConfig], int]:
        if self._lkg is None:
            return [], 0
        return _parse_registry_entries(self._lkg.get("rooms"), env)

    def _resolve_without_registry(
        self, env: dict
    ) -> tuple[list[RoomConfig], dict[str, Any]]:
        """No registry URL configured: serve the last-known-good if one
        exists (the operator paused the registry, not the estate), else
        today's ``PW_ROOMS`` env — unchanged."""
        checked_at = _iso_now()
        if self._lkg is not None:
            configs, dropped = self._configs_from_lkg(env)
            return configs, _registry_report(
                "last_known_good",
                "not_configured",
                checked_at,
                "registry not configured; serving last-known-good",
                self._lkg.get("updated_at"),
                dropped,
            )
        return (
            parse_rooms(env),
            _registry_report("env", "not_configured", checked_at, None, None, 0),
        )

    def _registry_failure(
        self, reason: str, checked_at: str, env: dict
    ) -> tuple[list[RoomConfig], dict[str, Any]]:
        """A failed registry read: last-known-good if present, else env."""
        if self._lkg is not None:
            configs, dropped = self._configs_from_lkg(env)
            return configs, _registry_report(
                "last_known_good",
                "unreachable",
                checked_at,
                reason,
                self._lkg.get("updated_at"),
                dropped,
            )
        return (
            parse_rooms(env),
            _registry_report("env", "unreachable", checked_at, reason, None, 0),
        )

    async def _fetch_registry(
        self, env: dict
    ) -> tuple[list[RoomConfig], dict[str, Any]]:
        """Fetch the registry once. Never raises; a failure falls back."""
        url = (env.get(REGISTRY_URL_ENV) or "").strip()
        checked_at = _iso_now()
        token_env_name = (env.get(REGISTRY_TOKEN_ENV_ENV) or "").strip()
        token = (env.get(token_env_name) or "").strip() if token_env_name else ""
        insecure = (env.get(REGISTRY_INSECURE_TLS_ENV) or "").strip() == "1"
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(REGISTRY_TIMEOUT_SECONDS),
                verify=not insecure,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                resp = await client.get(url, headers=headers)
        except Exception as exc:  # noqa: BLE001 — a dead registry must not break the estate
            return self._registry_failure(_reason(exc), checked_at, env)
        if not (200 <= resp.status_code < 300):
            return self._registry_failure(f"HTTP {resp.status_code}", checked_at, env)
        try:
            payload = resp.json()
        except (ValueError, UnicodeDecodeError):
            return self._registry_failure("malformed JSON", checked_at, env)
        parsed = _parse_registry_payload(payload, env)
        if parsed is None:
            return self._registry_failure(
                "registry payload has no rooms list", checked_at, env
            )
        configs, dropped = parsed
        updated_at = payload.get("updated_at")
        self._lkg = {
            "updated_at": updated_at if isinstance(updated_at, str) else None,
            "fetched_at": checked_at,
            "rooms": _lkg_entries(configs),
        }
        self._persist_registry_lkg()
        return configs, _registry_report(
            "registry", "ok", checked_at, None, self._lkg["updated_at"], dropped
        )

    async def _resolve_configs(
        self, env: dict
    ) -> tuple[list[RoomConfig], dict[str, Any]]:
        """Resolve this snapshot's rooms: registry (cached 60 s) with
        last-known-good and env fallbacks. Never raises."""
        url = (env.get(REGISTRY_URL_ENV) or "").strip()
        if not url:
            return self._resolve_without_registry(env)
        now = self._clock()
        if (
            self._resolved is not None
            and (now - self._resolved_at) < REGISTRY_CACHE_TTL_SECONDS
        ):
            return self._resolved
        resolved = await self._fetch_registry(env)
        self._resolved = resolved  # cache the attempt too: no hammering
        self._resolved_at = now
        return resolved

    def invalidate(self) -> None:
        """Drop the cached snapshot (tests and explicit refresh)."""
        self._cache = None
        self._cache_at = float("-inf")
        self._principal_cache.clear()
        self._secrets_cache = None
        self._secrets_cache_at = float("-inf")
        self._actions_cache.clear()

    def _invalidate_after_action(self, room_id: str, principal_id: str | None) -> None:
        """Forget the room's cached read state after a real change.

        A successful action (``ok: true``) means the room's cards/needs
        may now differ: the shared snapshot is dropped so the next
        ``GET /api/rooms`` re-reads the room (the need disappears), and
        this caller's per-person forwarded row is dropped with it. Only
        the caller whose action succeeded is forgotten — another
        person's own forwarded view was never affected by it.
        """
        self._cache = None
        self._cache_at = float("-inf")
        if principal_id is not None:
            self._principal_cache.pop((room_id, principal_id), None)
        self._forget_views(room_id)
        self._publish(room_id)

    # ── Live updates ────────────────────────────────────────────────

    def listen(self) -> asyncio.Queue:
        """A queue that receives ``{room, at}`` for every change."""
        q: asyncio.Queue = asyncio.Queue(maxsize=LISTENER_QUEUE)
        self._listeners.add(q)
        return q

    def unlisten(self, q: asyncio.Queue) -> None:
        self._listeners.discard(q)

    def _publish(self, room_id: str) -> None:
        event = {"room": room_id, "at": _iso_now()}
        for q in list(self._listeners):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # a slow screen misses a ping; its next one catches up

    def _forget_views(self, room_id: str) -> None:
        for key in [k for k in self._views_cache if k[0] == room_id]:
            self._views_cache.pop(key, None)

    async def room_changed(self, room_id: str, env: dict | None = None) -> bool:
        """A room says its data changed: drop everything cached for it and
        tell open screens. False for an unknown room. Pings closer together
        than :data:`PING_MIN_GAP_SECONDS` are folded into one (still True)."""
        if not isinstance(room_id, str) or not _VALID_ROOM_ID.match(room_id):
            return False
        if await self.resolved_config(room_id, env) is None:
            return False
        now = self._clock()
        if now - self._last_ping.get(room_id, float("-inf")) < PING_MIN_GAP_SECONDS:
            return True
        self._last_ping[room_id] = now
        self._cache = None
        self._cache_at = float("-inf")
        for key in [k for k in self._principal_cache if k[0] == room_id]:
            self._principal_cache.pop(key, None)
        self._actions_cache.pop(room_id, None)
        self._forget_views(room_id)
        self._publish(room_id)
        return True

    # ── Pictures (``GET /room/art/{name}.webp``) ───────────────────

    async def art(self, room_id: str, name: str, env: dict | None = None) -> bytes | None:
        """One of a room's pictures as WebP bytes, or None (bad name, unknown
        room, unreachable, not WebP, too big). Cached an hour; never raises."""
        env = os.environ if env is None else env
        if (
            not isinstance(room_id, str) or not _VALID_ROOM_ID.match(room_id)
            or not isinstance(name, str) or not _VALID_ART_NAME.match(name)
        ):
            return None
        key = (room_id, f"art:{name}", "")
        now = self._clock()
        hit = self._views_cache.get(key)
        if hit and now - hit[0] < ART_CACHE_SECONDS:
            return hit[2]
        config = await self.resolved_config(room_id, env)
        if config is None or config.contract not in SUPPORTED_CONTRACTS or config.invalid_reason is not None:
            return None
        headers = self._room_headers(config)
        headers["Accept"] = "image/webp"
        url = config.base_url.rstrip("/") + ART_PATH + f"/{name}.webp"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(VIEW_TIMEOUT_SECONDS),
                verify=not config.insecure_tls,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                resp = await client.get(url, headers=headers)
        except Exception:  # noqa: BLE001 — a dead room must not break the main app
            return None
        body = resp.content
        ok = (
            resp.status_code == 200
            and len(body) <= MAX_ART_BYTES
            and body[:4] == b"RIFF"
            and body[8:12] == b"WEBP"
        )
        data = body if ok else None
        if ok or resp.status_code == 404:
            self._views_cache[key] = (now, 200, data)
        return data

    # ── Libraries (Play-Nice ``library/0`` at ``GET /room/library``) ──

    async def libraries(self, principal: Any | None = None, env: dict | None = None) -> list[dict[str, Any]]:
        """Every connected room's library, one row per room that offers one.

        Only rooms whose descriptor lists ``library`` in ``offers`` are
        asked (ROOM rule 1: a front door uses only the extras a room lists).

        A row is ``{room, status, library?, error?}``: ``ok`` with the
        room's ``library/0`` document (checked for its shape, never
        rewritten), or ``unavailable`` with plain words when the room's
        library couldn't be read. A room without a library (404) has no
        row. Uses the view machinery: room token, size cap, 15 s cache
        that the room's change ping clears. Never raises.
        """
        env = os.environ if env is None else env
        configs, _ = await self._resolve_configs(env)
        snapshot = await self.snapshot(env)
        offering = {
            r.get("id") for r in snapshot
            if isinstance(r.get("room"), dict)
            and isinstance(r["room"].get("offers"), list)
            and "library" in r["room"]["offers"]
        }
        rows: list[dict[str, Any]] = []

        async def one(config: RoomConfig) -> None:
            status, payload = await self._fetch_json(config, LIBRARY_PATH, "library", principal)
            if status == 404:
                return
            if status == 200 and _is_library(payload):
                rows.append({"room": config.id, "status": "ok", "library": payload})
            else:
                rows.append({"room": config.id, "status": "unavailable",
                             "error": f"{config.id}'s library couldn't be read."})

        usable = [
            c for c in configs
            if c.id in offering and c.contract in SUPPORTED_CONTRACTS and c.invalid_reason is None
        ]
        await asyncio.gather(*(one(c) for c in usable))
        rows.sort(key=lambda r: r["room"])
        return rows

    async def sticker_sets(self, principal: Any | None = None, env: dict | None = None) -> list[dict[str, Any]]:
        """Every connected room's sticker set (``stickers/0``), one row per
        room whose descriptor lists ``stickers`` or ``views`` in ``offers``
        (the room contract's offers list doesn't name ``stickers`` yet, so a
        room may serve it as one of its views). A row is
        ``{room, status, set?, error?}``; a room with no set (404) has no
        row. Same machinery and rules as :meth:`libraries`. Never raises."""
        env = os.environ if env is None else env
        configs, _ = await self._resolve_configs(env)
        snapshot = await self.snapshot(env)
        offering = {
            r.get("id") for r in snapshot
            if isinstance(r.get("room"), dict)
            and isinstance(r["room"].get("offers"), list)
            and ({"stickers", "views"} & set(r["room"]["offers"]))
        }
        rows: list[dict[str, Any]] = []

        async def one(config: RoomConfig) -> None:
            status, payload = await self._fetch_json(config, STICKERS_PATH, "stickers", principal)
            if status == 404:
                return
            # Views may wrap their document ({generated_at, stickers: {...}}),
            # as Hive Works' views do; accept both shapes.
            if isinstance(payload, dict) and isinstance(payload.get("stickers"), dict):
                payload = payload["stickers"]
            if (status == 200 and isinstance(payload, dict)
                    and payload.get("contract") == "stickers/0"
                    and isinstance(payload.get("stickers"), list)):
                rows.append({"room": config.id, "status": "ok", "set": payload})
            else:
                rows.append({"room": config.id, "status": "unavailable",
                             "error": f"{config.id}'s stickers couldn't be read."})

        usable = [
            c for c in configs
            if c.id in offering and c.contract in SUPPORTED_CONTRACTS and c.invalid_reason is None
        ]
        await asyncio.gather(*(one(c) for c in usable))
        rows.sort(key=lambda r: r["room"])
        return rows

    async def _fetch_json(
        self, config: RoomConfig, path: str, cache_name: str, principal: Any | None
    ) -> tuple[int, Any]:
        principal_id = _safe_principal_id(getattr(principal, "id", None))
        who = principal_id if config.forward_principal else ""
        key = (config.id, cache_name, who or "")
        now = self._clock()
        hit = self._views_cache.get(key)
        if hit and now - hit[0] < VIEW_CACHE_SECONDS:
            return hit[1], hit[2]
        headers = self._room_headers(config, principal_id)
        headers["Accept"] = "application/json"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(VIEW_TIMEOUT_SECONDS),
                verify=not config.insecure_tls,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                resp = await client.get(config.base_url.rstrip("/") + path, headers=headers)
        except Exception:  # noqa: BLE001 — a dead room must not break the main app
            return 502, None
        if resp.status_code == 404:
            result: tuple[int, Any] = (404, None)
        elif not (200 <= resp.status_code < 300) or len(resp.content) > MAX_LIBRARY_BYTES:
            result = (502, None)
        else:
            try:
                result = (200, resp.json())
            except (ValueError, UnicodeDecodeError):
                result = (502, None)
        self._views_cache[key] = (now, result[0], result[1])
        return result

    # ── Read-only views (``GET /room/views/{name}[/{item}]``) ───────

    async def view(
        self,
        room_id: str,
        name: str,
        item: str | None = None,
        principal: Any | None = None,
        env: dict | None = None,
    ) -> tuple[int, Any]:
        """One read-only view from a room, e.g. Hive Works' ``projects``.

        Returns ``(http_status, payload)``: 200 with the room's JSON (an
        object or a list, at most :data:`MAX_VIEW_BYTES`), 404 for a bad
        or unknown room/view, 502 when the room can't be read. Uses the
        room's own token and TLS policy (principal forwarded only when the
        registry opted in), no redirects, a short timeout, and a
        :data:`VIEW_CACHE_SECONDS` cache that a change ping clears.
        Never raises on the room's behalf.
        """
        env = os.environ if env is None else env
        if (
            not isinstance(room_id, str) or not _VALID_ROOM_ID.match(room_id)
            or not isinstance(name, str) or not _VALID_VIEW_NAME.match(name)
            or (item is not None and (not isinstance(item, str) or not _VALID_VIEW_ITEM.match(item)))
        ):
            return 404, {"error": "No such view."}
        config = await self.resolved_config(room_id, env)
        if config is None or config.contract not in SUPPORTED_CONTRACTS or config.invalid_reason is not None:
            return 404, {"error": "No such room."}
        principal_id = _safe_principal_id(getattr(principal, "id", None))
        who = principal_id if config.forward_principal else ""
        key = (room_id, f"{name}/{item or ''}", who or "")
        now = self._clock()
        hit = self._views_cache.get(key)
        if hit and now - hit[0] < VIEW_CACHE_SECONDS:
            return hit[1], hit[2]
        url = config.base_url.rstrip("/") + VIEWS_PATH + "/" + name + (f"/{item}" if item else "")
        headers = self._room_headers(config, principal_id)
        headers["Accept"] = "application/json"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(VIEW_TIMEOUT_SECONDS),
                verify=not config.insecure_tls,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                resp = await client.get(url, headers=headers)
        except Exception:  # noqa: BLE001 — a dead room must not break the main app
            return 502, {"error": f"Couldn't reach {room_id}."}
        if resp.status_code == 404:
            result: tuple[int, Any] = (404, {"error": "No such view."})
        elif not (200 <= resp.status_code < 300) or len(resp.content) > MAX_VIEW_BYTES:
            result = (502, {"error": f"{room_id} didn't answer with that view."})
        else:
            try:
                payload = resp.json()
            except (ValueError, UnicodeDecodeError):
                payload = None
            if isinstance(payload, (dict, list)):
                result = (200, payload)
            else:
                result = (502, {"error": f"{room_id} didn't answer with that view."})
        self._views_cache[key] = (now, result[0], result[1])
        return result

    async def resolved_config(
        self, room_id: str, env: dict | None = None
    ) -> RoomConfig | None:
        """The resolved config for one room id, or ``None`` when unconfigured.

        Uses the same cached resolution a snapshot uses (registry 60 s,
        last-known-good, env fallback), so this never triggers a second
        registry round inside the cache window.
        """
        env = os.environ if env is None else env
        configs, _ = await self._resolve_configs(env)
        for config in configs:
            if config.id == room_id:
                return config
        return None

    async def secrets_overview(self, env: dict | None = None) -> dict[str, Any]:
        """The Secrets board's read-only data source. Never raises.

        Finds the room named ``workshop`` and reads its
        ``GET /api/secrets/summary`` with that room's token and TLS policy
        (3 s timeout, cached 60 s). Names and health only — never a secret
        value. Any failure — the room missing, unreachable, refusing the
        read (401), or answering malformed — is reported as
        ``station.status: "unknown"`` with a plain-words detail and empty
        lists; the response never invents namespaces or keys and never
        carries a token or a value.
        """
        env = os.environ if env is None else env
        now = self._clock()
        if (
            self._secrets_cache is not None
            and (now - self._secrets_cache_at) < SECRETS_CACHE_TTL_SECONDS
        ):
            return self._secrets_cache
        data = await self._fetch_secrets_overview(env)
        self._secrets_cache = data
        self._secrets_cache_at = now
        return data

    async def _fetch_secrets_overview(self, env: dict) -> dict[str, Any]:
        config = await self.resolved_config(SECRETS_ROOM_ID, env)
        if config is None:
            return _unknown_secrets_overview(
                f"the room {SECRETS_ROOM_ID!r} is not in the registry"
            )
        if config.contract not in SUPPORTED_CONTRACTS:
            return _unknown_secrets_overview(
                f"the {SECRETS_ROOM_ID} room speaks an unsupported "
                f"contract {config.contract!r}",
                config,
            )
        if config.invalid_reason is not None:
            return _unknown_secrets_overview(
                f"the {SECRETS_ROOM_ID} room's address is unusable "
                f"({config.invalid_reason})",
                config,
            )

        base = config.base_url.rstrip("/")
        headers = {"Accept": "application/json"}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(SECRETS_TIMEOUT_SECONDS),
                verify=not config.insecure_tls,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                resp = await client.get(base + SECRETS_SUMMARY_PATH, headers=headers)
        except Exception as exc:  # noqa: BLE001 — a dead station must not break the board
            return _unknown_secrets_overview(_reason(exc), config)
        if resp.status_code == 401:
            return _unknown_secrets_overview(
                "the room refused the read (401 unauthorized)", config
            )
        if not (200 <= resp.status_code < 300):
            return _unknown_secrets_overview(
                f"the room answered HTTP {resp.status_code}", config
            )
        try:
            payload = resp.json()
        except (ValueError, UnicodeDecodeError):
            return _unknown_secrets_overview(
                "the room answered malformed JSON", config
            )
        if not isinstance(payload, dict):
            return _unknown_secrets_overview(
                "the room's summary is not an object", config
            )
        return _sanitize_secrets_summary(payload, config)

    async def perform_action(
        self,
        room_id: str,
        action_id: str,
        principal: Any | None,
        idempotency_key: str | None,
        body: bytes | None = None,
        env: dict | None = None,
        allow_write: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        """Pass one room/0 action through to its room; return a receipt.

        Returns ``(http_status, receipt)``. The receipt is always the
        allow-listed shape (:data:`RECEIPT_FIELDS`) — the room's own when
        it answered with one, or a local one otherwise. Rules,
        in order:

        * a malformed room/action id, an unconfigured/disabled room, an
          unsupported contract or an unusable address is refused locally
          (404) before any network call;
        * the room's own ``GET /room/actions`` list (cached 60 s per
          room) decides whether the action exists (404 when not) and
          whether it is a write; a write requires the caller to hold the
          ``approve`` permission (403 otherwise), and a missing/unknown
          ``writes`` field is treated as a write (fail closed). The
          caller may pass ``allow_write=True`` when a live helper grant's
          ``act_for`` already authorized the write for this person; the
          default is False, so an ordinary caller is unchanged;
        * a missing/malformed ``Idempotency-Key`` is refused (400), a
          body over 16 KB is refused (413), and a non-object JSON body is
          refused (400);
        * otherwise the call goes out to ``POST /room/actions/{id}``
          with the room's own token, the caller's ``X-Worlds-Principal``
          (always, when the room has a token), the room's owner token as
          ``X-Worlds-Owner-Token`` (only when one is configured for this
          room AND the action writes — :data:`OWNER_HEADER`), and the
          idempotency key, with a 10 s timeout and no retries.

        A room that answers with a receipt-shaped body is passed through
        with HTTP 200 whatever its status code (the receipt's own ``ok``
        says whether anything changed). A room that cannot be reached,
        times out, fails, or answers something that is not a receipt gets
        an ``ok: false`` receipt with HTTP 200 — this method never
        raises on a room's behalf. ``PW_API_TOKEN`` and the human session
        are never sent. After a receipt with ``ok: true`` the shared
        snapshot (and this caller's forwarded row) is dropped so the next
        ``GET /api/rooms`` re-reads the room.
        """
        env = os.environ if env is None else env
        asked = action_id if isinstance(action_id, str) else ""

        # 1. Address rules, before any network. A bad id never becomes a
        # probe of an unvalidated URL (the room-id rule is the registry's;
        # the action-id rule is the interface's).
        if not isinstance(room_id, str) or not _VALID_ROOM_ID.match(room_id):
            return 404, _receipt(asked, False, "No such room.")
        if not isinstance(action_id, str) or not _VALID_ACTION_ID.match(action_id):
            return 404, _receipt(asked, False, "That room doesn't offer that.")

        # 2. The room must be configured, enabled and understood. A
        # registry ``enabled: false`` entry is never resolved; an
        # unsupported contract or unusable address is refused here.
        config = await self.resolved_config(room_id, env)
        if (
            config is None
            or config.contract not in SUPPORTED_CONTRACTS
            or config.invalid_reason is not None
        ):
            return 404, _receipt(asked, False, "No such room.")

        principal_id = _safe_principal_id(getattr(principal, "id", None))

        # 3. Writes need the `approve` permission (owner and admin hold
        # it; helpers will hold it for one person in step 2). The room's
        # own list is authoritative: an unreadable list or an unknown
        # action fails closed (404); a missing ``writes`` is treated as a
        # write (never guessed safe).
        actions = await self._room_actions(config)
        action = (
            next((a for a in actions if a.get("id") == action_id), None)
            if actions is not None
            else None
        )
        if action is None:
            return 404, _receipt(asked, False, "That room doesn't offer that.")
        if (
            action.get("writes") is not False
            and not allow_write
            and not can(principal, "approve")
        ):
            return 403, _receipt(asked, False, "Only the owner can do that here.")

        # 4. A retry must not double-act: the caller presents a key.
        if (
            not isinstance(idempotency_key, str)
            or not IDEMPOTENCY_VALUE_RE.match(idempotency_key)
        ):
            return 400, _receipt(
                asked,
                False,
                "An Idempotency-Key header (1-128 chars of "
                "A-Za-z0-9._:-) is required.",
            )

        # 5. A JSON object body, at most 16 KB, forwarded byte-for-byte
        # (the action's own arguments are the room's business).
        raw = body or b""
        if len(raw) > MAX_ACTION_BODY_BYTES:
            return 413, _receipt(
                asked, False, "The action body is larger than 16 KB."
            )
        if raw and not _is_json_object(raw):
            return 400, _receipt(
                asked, False, "The action body must be a JSON object."
            )

        # 6. The outbound call. The room's own token authenticates Worlds;
        # the principal header says *who* asked. It rides always when the
        # room has a token — an action is always someone's — unlike reads,
        # where it depends on the room's forward_principal opt-in. The
        # human's session / PW_API_TOKEN is never among these.
        #
        # A room may additionally require an owner token on a write:
        # X-Worlds-Principal is client-supplied and not cryptographically
        # bound to the caller, so it cannot by itself authorize an
        # owner-only action (hive-works, 2026-09-28). This is generic —
        # keyed by the action's own ``writes`` flag (step 3's same rule),
        # not by room id or action id — so it applies to any room/0 room
        # that configures PW_ROOM_<ID>_OWNER_TOKEN_ENV, not only
        # hive-works. No owner token configured for this room means the
        # header is never sent.
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
            if principal_id is not None:
                headers[PRINCIPAL_HEADER] = principal_id
            if config.owner_token and action.get("writes") is not False:
                headers[OWNER_HEADER] = config.owner_token
        url = config.base_url.rstrip("/") + ACTIONS_PATH + "/" + action_id
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(ACTION_TIMEOUT_SECONDS),
                verify=not config.insecure_tls,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                resp = await client.post(url, headers=headers, content=raw)
        except Exception:  # noqa: BLE001 — a dead room must not break the main app
            return 200, self._action_failure(config, action_id)
        try:
            payload = resp.json()
        except (ValueError, UnicodeDecodeError):
            return 200, self._action_failure(config, action_id)
        receipt = _sanitize_receipt(payload, action_id)
        if receipt is None:
            return 200, self._action_failure(config, action_id)
        if receipt["ok"]:
            # The room changed something: the need must disappear on the
            # next /api/rooms, and this caller's forwarded view with it.
            self._invalidate_after_action(config.id, principal_id)
        return 200, receipt

    async def _room_actions(
        self, config: RoomConfig
    ) -> list[dict[str, Any]] | None:
        """The room's own action list, cached 60 s per room (never per
        person — the list is estate-wide). ``None`` is a "could
        not read it"; the caller fails closed. A failed read is cached
        too, so a dead room is not hammered."""
        now = self._clock()
        cached = self._actions_cache.get(config.id)
        if cached is not None and (now - cached[0]) < ACTIONS_CACHE_TTL_SECONDS:
            return cached[1]
        actions = await self._fetch_room_actions(config)
        self._actions_cache[config.id] = (now, actions)
        return actions

    async def _attach_actions(
        self, configs: list[RoomConfig], rows: list[dict[str, Any]]
    ) -> None:
        """Put each room's own actions on its row as ``[{id, title, writes}]``
        (plus ``fields`` for a small form and ``need_bound`` for actions that
        answer one need; see :func:`_action_form`)
        (from the 60 s action cache), so the UI can offer room-level
        actions such as "Re-check the tickets". An unreachable room, or one
        whose list can't be read, gets ``[]``; ``writes`` is ``None`` when
        the room didn't say (the UI treats that as a write)."""
        by_id = {c.id: c for c in configs}

        async def one(row: dict[str, Any]) -> None:
            config = by_id.get(row.get("id"))
            if config is None or not row.get("reachable"):
                row["actions"] = []
                return
            listed = await self._room_actions(config) or []
            out = []
            for a in listed:
                aid = a.get("id")
                if not isinstance(aid, str) or not aid:
                    continue
                title = a.get("label") or a.get("title") or aid
                writes = a.get("writes")
                entry: dict[str, Any] = {
                    "id": aid,
                    "title": str(title),
                    "writes": writes if isinstance(writes, bool) else None,
                }
                fields, need_bound = _action_form(a.get("input_schema"))
                if fields:
                    entry["fields"] = fields
                if need_bound:
                    entry["need_bound"] = True
                out.append(entry)
            row["actions"] = out

        await asyncio.gather(*(one(r) for r in rows))

    async def _fetch_room_actions(
        self, config: RoomConfig
    ) -> list[dict[str, Any]] | None:
        """Read ``GET /room/actions`` once, with the room's token/TLS
        policy (2 s, like the other reads). Never raises."""
        base = config.base_url.rstrip("/")
        # Estate-wide list: no principal header (it is not per person and
        # is shared across callers by the 60 s cache).
        headers = self._room_headers(config)
        headers["Accept"] = "application/json"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(TIMEOUT_SECONDS),
                verify=not config.insecure_tls,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                resp = await client.get(base + ACTIONS_PATH, headers=headers)
        except Exception:  # noqa: BLE001 — a dead room must not break the main app
            return None
        if not (200 <= resp.status_code < 300):
            return None
        try:
            payload = resp.json()
        except (ValueError, UnicodeDecodeError):
            return None
        return _parse_room_actions(payload)

    def _action_failure(self, config: RoomConfig, action_id: str) -> dict[str, Any]:
        """The "nothing changed" receipt for a room that could not
        answer with a receipt of its own."""
        name = config.name or config.id
        return _receipt(
            action_id, False, f"Couldn't reach {name}, so nothing changed."
        )

    async def snapshot(self, env: dict | None = None) -> list[dict[str, Any]]:
        """One row per resolved room. Never raises."""
        env = os.environ if env is None else env
        now = self._clock()
        if self._cache is not None and (now - self._cache_at) < CACHE_TTL_SECONDS:
            return self._cache
        configs, report = await self._resolve_configs(env)
        self._registry_report = report
        self._last_configs = configs
        rows = list(await asyncio.gather(*(self._probe(c) for c in configs)))
        await self._attach_actions(configs, rows)
        self._cache = rows
        self._cache_at = now
        self._persist()  # room health outlives this process
        return rows

    async def snapshot_for_principal(
        self, principal: Any | None = None, env: dict | None = None
    ) -> list[dict[str, Any]]:
        """The caller's rows: shared rows plus the caller's own forwarded rows.

        Non-forwarding rooms come straight from the one shared 15 s
        snapshot — unchanged. For a forwarding room (registry
        ``forward_principal: true`` AND a configured token) the row's
        cards and needs are replaced with this principal's own forwarded
        fetch (cached per room + principal, same 15 s TTL). The room's
        status, reachability and last-seen stay estate-wide, because a
        room that is down is down for everyone. A principal with no
        usable id, or no forwarding rooms, gets exactly the shared rows:
        one principal's forwarded fetch can never appear in another's.

        This is the caller-aware entry point for ``GET /api/rooms`` and the
        briefing. :meth:`snapshot` (no principal) is what background
        jobs and the digest use: forwarding rooms answer it with their
        own default, non-personal view because the header is not sent.
        """
        env = os.environ if env is None else env
        rows = await self.snapshot(env)
        principal_id = _safe_principal_id(getattr(principal, "id", None))
        if principal_id is None:
            return rows
        configs = self._last_configs or []
        forwarding = [c for c in configs if c.forward_principal and c.token]
        if not forwarding:
            return rows
        fetched = await asyncio.gather(
            *(self._forwarded_row(c, principal_id) for c in forwarding)
        )
        by_id = {row["id"]: row for row in fetched}
        merged: list[dict[str, Any]] = []
        for row in rows:
            forwarded = by_id.get(row["id"])
            merged.append(
                _merge_personal(row, forwarded) if forwarded is not None else row
            )
        return merged

    async def _forwarded_row(
        self, config: RoomConfig, principal_id: str
    ) -> dict[str, Any]:
        """The cached per-principal row for one forwarding room."""
        key = (config.id, principal_id)
        now = self._clock()
        cached = self._principal_cache.get(key)
        if cached is not None and (now - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]
        row = await self._probe(config, principal_id=principal_id)
        self._store_principal_row(key, principal_id, row, now)
        return row

    def _store_principal_row(
        self, key: tuple[str, str], principal_id: str, row: dict[str, Any], now: float
    ) -> None:
        """Cache one forwarded row, evicting the oldest principal past the cap."""
        self._principal_cache.pop(key, None)
        self._principal_cache[key] = (now, row)
        order: list[str] = []
        for _, pid in self._principal_cache:
            if pid not in order:
                order.append(pid)
        while len(order) > MAX_FORWARD_PRINCIPALS:
            oldest = order.pop(0)
            for cache_key in [k for k in self._principal_cache if k[1] == oldest]:
                del self._principal_cache[cache_key]

    def _room_headers(
        self, config: RoomConfig, principal_id: str | None = None
    ) -> dict[str, str]:
        """Outbound headers for one room request.

        Always the room's own bearer token when it has one. The
        ``X-Worlds-Principal`` header is added **in addition** to that
        token — never instead of it — only when the registry opted the
        room in, the room has a token, and the principal id is safe. A
        room with no token gets no identity claim (meaningless without
        authentication), so it behaves as non-forwarding. The human's
        session token / ``PW_API_TOKEN`` is never among these. Any future
        ``POST /room/actions/*`` must use this same helper.
        """
        headers: dict[str, str] = {}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
            if (
                config.forward_principal
                and principal_id
                and _SAFE_PRINCIPAL_ID.match(principal_id)
            ):
                headers[PRINCIPAL_HEADER] = principal_id
        return headers

    async def _probe(
        self, config: RoomConfig, principal_id: str | None = None
    ) -> dict[str, Any]:
        checked_at = _iso_now()
        if config.contract not in SUPPORTED_CONTRACTS:
            # A registry entry this main app cannot understand: never
            # loaded, never healthy, and its cards/needs are nothing.
            return self._row(
                config,
                reachable=False,
                room=None,
                cards=[],
                needs_you=[],
                error=f"unsupported contract {config.contract!r}",
                status=INCOMPATIBLE,
                checked_at=checked_at,
            )
        if config.invalid_reason is not None:
            return self._row(
                config,
                reachable=False,
                room=None,
                cards=[],
                needs_you=[],
                error=config.invalid_reason,
                status=UNREACHABLE,
                checked_at=checked_at,
            )

        base = config.base_url.rstrip("/")
        headers = self._room_headers(config, principal_id)

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(TIMEOUT_SECONDS),
                verify=not config.insecure_tls,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                descriptor_resp, cards_resp, needs_resp = await asyncio.gather(
                    client.get(base + ROOM_PATH, headers=headers),
                    client.get(base + CARDS_PATH, headers=headers),
                    client.get(base + NEEDS_YOU_PATH, headers=headers),
                    return_exceptions=True,
                )
        except Exception as exc:  # noqa: BLE001 — a dead room must not break the estate
            return self._unreachable(config, _reason(exc), checked_at)

        needs_you, needs_error = _parse_needs_you(needs_resp)
        cards, cards_error = _parse_cards(cards_resp)

        if isinstance(descriptor_resp, BaseException):
            return self._unreachable(config, _reason(descriptor_resp), checked_at)
        if not (200 <= descriptor_resp.status_code < 300):
            return self._unreachable(
                config, f"HTTP {descriptor_resp.status_code}", checked_at
            )
        try:
            descriptor = descriptor_resp.json()
        except (ValueError, UnicodeDecodeError):
            return self._unreachable(config, "malformed JSON", checked_at)
        if not isinstance(descriptor, dict):
            return self._unreachable(config, "descriptor is not an object", checked_at)

        contract = descriptor.get("contract")
        if contract is not None and contract not in SUPPORTED_CONTRACTS:
            # Rule 14: a consumer that does not understand a contract
            # value fails clearly rather than guessing. The room answered
            # — it is reachable — but its descriptor, cards and needs are
            # not rendered and never counted.
            return self._row(
                config,
                reachable=True,
                room=None,
                cards=[],
                needs_you=[],
                error=f"unexpected contract {contract!r}",
                status=INCOMPATIBLE,
                checked_at=checked_at,
            )

        raw_status = descriptor.get("status")
        status = raw_status if raw_status in ROOM_STATUSES else "unknown"
        return self._row(
            config,
            reachable=True,
            room=descriptor,
            cards=cards,
            needs_you=needs_you,
            error=needs_error or cards_error,
            status=status,
            checked_at=checked_at,
        )

    def _unreachable(
        self, config: RoomConfig, error: str, checked_at: str
    ) -> dict[str, Any]:
        return self._row(
            config,
            reachable=False,
            room=None,
            cards=[],
            needs_you=[],
            error=error,
            status=UNREACHABLE,
            checked_at=checked_at,
        )

    def _row(
        self,
        config: RoomConfig,
        *,
        reachable: bool,
        room: dict | None,
        cards: list,
        needs_you: list,
        error: str | None,
        status: str,
        checked_at: str,
    ) -> dict[str, Any]:
        if reachable:
            self._last_seen[config.id] = checked_at
            # Only a declared, understood status is remembered; an
            # incompatible descriptor declares no usable status, so the
            # last real one is kept.
            if status in ROOM_STATUSES:
                self._last_status[config.id] = status
            self._dirty = True
        return {
            "id": config.id,
            "base_url": config.base_url,
            "public_url": config.public_url,
            "reachable": reachable,
            "status": status,
            "room": room,
            "cards": cards,
            "needs_you": needs_you,
            "error": error,
            "checked_at": checked_at,
            "last_seen": self._last_seen.get(config.id),
            # The last status this room declared when it answered; null
            # only when it has truly never answered. Distinct from
            # ``status``, which is "unreachable" for a room that is down.
            "last_status": self._last_status.get(config.id),
        }


def _parse_cards(resp: Any) -> tuple[list, str | None]:
    """``(cards, error)`` from a cards response or exception.

    Same setting as ``_parse_needs_you``: a reachable room whose cards
    list is unreadable is still reachable; the failure is named and
    ``cards`` stays empty — never invented. Malformed individual cards
    are dropped rather than crashing the estate; a card the contract
    would treat as ``update`` (no/unknown tone) is still a card.
    """
    if isinstance(resp, BaseException):
        return [], _reason(resp)
    if not (200 <= resp.status_code < 300):
        return [], f"cards HTTP {resp.status_code}"
    try:
        payload = resp.json()
    except (ValueError, UnicodeDecodeError):
        return [], "cards malformed JSON"
    if not isinstance(payload, list):
        return [], "cards is not a list"
    return [c for c in payload if isinstance(c, dict)], None


def _parse_needs_you(resp: Any) -> tuple[list, str | None]:
    """``(needs, error)`` from a needs-you response or exception.

    A reachable room whose needs list is unreadable is still reachable;
    the failure is named in the row's ``error`` and ``needs_you`` stays
    empty — never invented.
    """
    if isinstance(resp, BaseException):
        return [], _reason(resp)
    if not (200 <= resp.status_code < 300):
        return [], f"needs-you HTTP {resp.status_code}"
    try:
        payload = resp.json()
    except (ValueError, UnicodeDecodeError):
        return [], "needs-you malformed JSON"
    if not isinstance(payload, list):
        return [], "needs-you is not a list"
    return payload, None
