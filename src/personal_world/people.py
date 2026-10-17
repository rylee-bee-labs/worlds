"""The People screens' state: invites, helper grants, limits, helper log.

Step 2 of the roles plan (owner-approved 2026-09-26). Step 1
(``roles.py``, ``identity.py``) gave every person a role and one
permission question. This module holds the small identity-level stores
the People screens need:

* **invites** — a one-time link token to join; only its hash is stored,
  and the plain token is returned exactly once, at creation.
* **helper grants** — one person lets another see their room needs
  (``see_needs_of``) and, when ``can_act`` is set, act for them
  (``act_for``). A grant expires; an expired grant is ignored everywhere.
* **limits** — the closed set of supervised limits, with who set them
  and when.
* **helper log** — what a helper did for a person, so the person can see
  it (the "helped by" view).

All four are identity-level metadata (like ``users.json``), not personal
content: they name people and permissions, never a journal, a world or a
secret. Storage rides the same atomic JSON entry point every other
Worlds state file uses. Nothing here reads or writes another person's
content.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Roles an invite may carry. ``owner`` is deliberately absent: ownership
#: is handed over through ``transfer-ownership`` and is never invited.
INVITE_ROLES: tuple[str, ...] = ("member", "supervised", "guest", "admin")

#: An invite link lasts 72 hours by default, and never more than 336.
DEFAULT_INVITE_HOURS = 72
MAX_INVITE_HOURS = 336

#: A helper grant lasts 7 days by default, and never more than 30.
DEFAULT_HELPER_DAYS = 7
MAX_HELPER_DAYS = 30

#: The closed set of supervised limit keys.
LIMIT_KEYS: tuple[str, ...] = (
    "chat_quiet_hours",
    "no_outside_sharing",
    "content_boundary",
)

#: The closed set of values for ``content_boundary``.
CONTENT_BOUNDARIES: tuple[str, ...] = ("gentle", "standard")

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


# ── time helpers ─────────────────────────────────────────────────────


def iso_now() -> str:
    """Now, as an ISO-8601 UTC string ending in ``Z``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_iso(epoch: float) -> str:
    """An epoch time as an ISO-8601 UTC string ending in ``Z``."""
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: Any) -> float | None:
    """A timestamp from an ISO-8601 string, or ``None`` if unreadable."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def _fingerprint(token: str) -> str:
    """sha256 of a high-entropy token. The plain token is never stored."""
    return hashlib.sha256(token.encode()).hexdigest()


def slug_user_id(display_name: str) -> str:
    """A safe account id made from a display name.

    Lower-case letters, digits, ``.``, ``-`` and ``_``; anything else
    becomes a hyphen. An empty or unusable result becomes ``invitee`` so
    the caller always has a valid starting point (it still checks the id
    is free before using it).
    """
    base = re.sub(r"[^a-z0-9]+", "-", (display_name or "").lower()).strip("-")
    base = base[:40].strip("-")
    if not base or not _SAFE_ID.match(base):
        return "invitee"
    return base


# ── closed-set validation ────────────────────────────────────────────


def valid_quiet_hours(value: Any) -> bool:
    """True only for ``"HH:MM-HH:MM"`` with two real 24-hour times."""
    if not isinstance(value, str):
        return False
    start, sep, end = value.partition("-")
    return bool(sep) and bool(_HHMM.match(start)) and bool(_HHMM.match(end))


def validate_limits(raw: Any) -> dict[str, Any]:
    """A ``[{key, value}]`` list as a checked ``{key: value}`` map.

    Fails closed with a plain ``ValueError`` message: a non-list, an
    unknown key, a duplicate key, or a value outside the key's closed set
    is refused rather than stored.
    """
    if not isinstance(raw, list):
        # ValueError on purpose: the route catches it and answers 422.
        raise ValueError("limits must be a list of {key, value}")  # noqa: TRY004
    out: dict[str, Any] = {}
    for item in raw:
        if not isinstance(item, dict):
            # ValueError on purpose: the route catches it and answers 422.
            raise ValueError(  # noqa: TRY004
                "each limit must be an object with key and value"
            )
        key = item.get("key")
        if key not in LIMIT_KEYS:
            raise ValueError("unknown limit key")
        if key in out:
            raise ValueError(f"limit {key} is listed twice")
        value = item.get("value")
        if key == "chat_quiet_hours":
            if not valid_quiet_hours(value):
                raise ValueError("chat_quiet_hours must look like 21:00-07:00")
        elif key == "no_outside_sharing":
            if not isinstance(value, bool):
                raise ValueError("no_outside_sharing must be true or false")
        elif key == "content_boundary" and value not in CONTENT_BOUNDARIES:
            raise ValueError("content_boundary must be gentle or standard")
        out[key] = value
    return out


# ── one small atomic JSON store, shared shape ────────────────────────


class _JsonStore:
    """A tiny atomic JSON store. Subclasses name their file and key."""

    filename = "store.json"
    root_key = "items"

    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / self.filename

    def _load(self) -> dict:
        if not self.path.exists():
            return {self.root_key: {}}
        try:
            payload = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {self.root_key: {}}
        if not isinstance(payload, dict):
            return {self.root_key: {}}
        return payload

    def _save(self, payload: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        os.replace(tmp, self.path)


# ── invites ──────────────────────────────────────────────────────────


class InviteStore(_JsonStore):
    """One-time invite links. Only the token's hash is ever stored."""

    filename = "invites.json"
    root_key = "invites"

    def _invites(self, payload: dict) -> list[dict]:
        invites = payload.get(self.root_key)
        return invites if isinstance(invites, list) else []

    def create(
        self,
        *,
        role: str,
        display_name: str,
        expires_at: float,
        created_by: str,
        guest_until: str | None = None,
    ) -> tuple[dict, str]:
        """Make an invite. Returns ``(record, plain_token)``.

        The plain token is returned here and nowhere else; the record
        keeps only its hash.
        """
        token = secrets.token_urlsafe(32)
        invite = {
            "invite_id": "inv-" + secrets.token_hex(6),
            "role": role,
            "display_name": display_name,
            "token_hash": _fingerprint(token),
            "created_at": iso_now(),
            "expires_at": expires_at,
            "guest_until": guest_until,
            "used_at": None,
            "created_by": created_by,
        }
        payload = self._load()
        # Assign the normalized list back explicitly: the shared _load
        # default shape is a dict, and the first invite must still land
        # as a list (same entry point HelperStore.create uses).
        invites = self._invites(payload)
        invites.append(invite)
        payload[self.root_key] = invites
        self._save(payload)
        return invite, token

    def list(self) -> list[dict]:
        """Every invite, newest first, with no token material at all."""
        invites = list(self._invites(self._load()))
        invites.sort(key=lambda i: i.get("created_at") or "", reverse=True)
        return [self._public(i) for i in invites]

    def find_by_token(self, token: str) -> dict | None:
        """The invite whose stored hash matches ``token``, or ``None``."""
        if not token:
            return None
        wanted = _fingerprint(token)
        for invite in self._invites(self._load()):
            if isinstance(invite.get("token_hash"), str) and secrets.compare_digest(
                wanted, invite["token_hash"]
            ):
                return invite
        return None

    def get(self, invite_id: str) -> dict | None:
        for invite in self._invites(self._load()):
            if invite.get("invite_id") == invite_id:
                return invite
        return None

    def mark_used(self, invite_id: str) -> bool:
        """Mark an invite used (single-use). Fail closed when unknown."""
        payload = self._load()
        for invite in self._invites(payload):
            if invite.get("invite_id") == invite_id:
                if invite.get("used_at"):
                    return False
                invite["used_at"] = iso_now()
                self._save(payload)
                return True
        return False

    def delete(self, invite_id: str) -> bool:
        payload = self._load()
        invites = self._invites(payload)
        kept = [i for i in invites if i.get("invite_id") != invite_id]
        if len(kept) == len(invites):
            return False
        payload[self.root_key] = kept
        self._save(payload)
        return True

    @staticmethod
    def _public(invite: dict) -> dict:
        """The allow-listed row: no token hash, ever."""
        expires_at = invite.get("expires_at")
        return {
            "invite_id": invite.get("invite_id"),
            "role": invite.get("role"),
            "display_name": invite.get("display_name"),
            "created_at": invite.get("created_at"),
            "expires_at": expires_at,
            "guest_until": invite.get("guest_until"),
            "used_at": invite.get("used_at"),
            "created_by": invite.get("created_by"),
            "expired": not isinstance(expires_at, (int, float))
            or expires_at <= time.time(),
        }


# ── helper grants ────────────────────────────────────────────────────


class HelperStore(_JsonStore):
    """Per-person helper grants. The person grants; an owner may revoke."""

    filename = "helper-grants.json"
    root_key = "grants"

    def _grants(self, payload: dict) -> list[dict]:
        grants = payload.get(self.root_key)
        return grants if isinstance(grants, list) else []

    @staticmethod
    def is_live(grant: dict, now: float | None = None) -> bool:
        """A grant counts only when it is not revoked and not expired."""
        if grant.get("revoked_at"):
            return False
        until = parse_iso(grant.get("until"))
        if until is None:
            return False
        return until > (now if now is not None else time.time())

    def create(
        self,
        *,
        person_id: str,
        helper_id: str,
        can_act: bool,
        until: str,
        created_by: str,
    ) -> dict:
        """Add a grant, or refresh the live one for the same pair.

        One live grant per (person, helper): granting again updates that
        grant's window and ``can_act`` rather than stacking a second one.
        """
        payload = self._load()
        grants = self._grants(payload)
        for grant in grants:
            if (
                grant.get("person_id") == person_id
                and grant.get("helper_id") == helper_id
                and self.is_live(grant)
            ):
                grant["can_act"] = bool(can_act)
                grant["until"] = until
                grant["created_at"] = iso_now()
                grant["created_by"] = created_by
                self._save(payload)
                return grant
        grant = {
            "grant_id": "grant-" + secrets.token_hex(6),
            "person_id": person_id,
            "helper_id": helper_id,
            "can_act": bool(can_act),
            "created_at": iso_now(),
            "until": until,
            "revoked_at": None,
            "revoked_by": None,
            "created_by": created_by,
        }
        grants.append(grant)
        payload[self.root_key] = grants
        self._save(payload)
        return grant

    def list_granted_by(self, person_id: str) -> list[dict]:
        """Every grant a person has issued, live or revoked, newest first.

        Revoked grants stay visible so the person can see a revocation
        that happened without them — the owner's emergency revocation.
        """
        grants = [
            g
            for g in self._grants(self._load())
            if g.get("person_id") == person_id
        ]
        grants.sort(key=lambda g: g.get("created_at") or "", reverse=True)
        return grants

    def live_for_helper(self, helper_id: str) -> list[dict]:
        """The live grants held by a helper. Expired ones are dropped."""
        now = time.time()
        return [
            g
            for g in self._grants(self._load())
            if g.get("helper_id") == helper_id and self.is_live(g, now)
        ]

    def get(self, grant_id: str) -> dict | None:
        for grant in self._grants(self._load()):
            if grant.get("grant_id") == grant_id:
                return grant
        return None

    def revoke(self, grant_id: str, by: str) -> dict | None:
        """Revoke a grant. Any time for the person; emergency for owner."""
        payload = self._load()
        for grant in self._grants(payload):
            if grant.get("grant_id") == grant_id:
                if grant.get("revoked_at"):
                    return grant
                grant["revoked_at"] = iso_now()
                grant["revoked_by"] = by
                self._save(payload)
                return grant
        return None


# ── supervised limits ────────────────────────────────────────────────


class LimitsStore(_JsonStore):
    """The supervised limit set per person, with who set it and when."""

    filename = "limits.json"
    root_key = "people"

    def get(self, person_id: str) -> dict | None:
        people = self._load().get(self.root_key)
        if not isinstance(people, dict):
            return None
        record = people.get(person_id)
        return record if isinstance(record, dict) else None

    def set(self, person_id: str, limits: dict[str, Any], set_by: str) -> dict:
        payload = self._load()
        people = payload.get(self.root_key)
        if not isinstance(people, dict):
            people = {}
        record = {
            "limits": limits,
            "set_by": set_by,
            "set_at": iso_now(),
        }
        people[person_id] = record
        payload[self.root_key] = people
        self._save(payload)
        return record


# ── helper log ("helped by") ─────────────────────────────────────────


class HelperLog(_JsonStore):
    """What helpers did for a person, so the person can see it."""

    filename = "helper-log.json"
    root_key = "people"

    #: At most this many recent entries are kept per person.
    MAX_ENTRIES = 200

    def append(self, person_id: str, entry: dict) -> None:
        payload = self._load()
        people = payload.get(self.root_key)
        if not isinstance(people, dict):
            people = {}
        entries = people.get(person_id)
        if not isinstance(entries, list):
            entries = []
        entries.append(entry)
        people[person_id] = entries[-self.MAX_ENTRIES :]
        payload[self.root_key] = people
        self._save(payload)

    def list(self, person_id: str) -> list[dict]:
        people = self._load().get(self.root_key)
        if not isinstance(people, dict):
            return []
        entries = people.get(person_id)
        if not isinstance(entries, list):
            return []
        # Newest first: the person sees the latest help at the top.
        return list(reversed(entries[-self.MAX_ENTRIES :]))
