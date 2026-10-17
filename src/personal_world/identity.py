"""Principal resolution: the single identity entry point.

Every protected route sees only a Principal (id, kind, owner_id,
scopes, auth_level, source). The trust root is local users
(Phase 1, Option B in the multi-user review 2026-09-09); OIDC is a
later authentication source that maps onto the same records. Perimeter
headers are never authorization, only possible login convenience.

Identity modes via PW_IDENTITY_MODE ("single" | "multi"):
- "single" (default): the legacy single-token gate continues to work.
  The principal is the instance bootstrap person, id "primary". Agent
  tokens (POST /api/identity/agents, which is not mode-gated) still
  resolve to their agent principal in this mode -- only person/user
  tokens are confined to the single instance-token gate.
- "multi": tokens are in data/users.json (hashed); each token maps
  to exactly one local user (or agent principal).

The single-user install remains byte-identical after every phase.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .roles import ROLES, can, role_for_groups

_logger = logging.getLogger("personal_world.identity")

Kind = Literal["person", "agent", "service"]

#: The bootstrap person's id: the install's first account and break-glass
#: owner. Not a name — this is the one fixed principal id.
BOOTSTRAP_PRINCIPAL_ID = "primary"


@dataclass(frozen=True)
class Principal:
    """The identity that reached the handler. Scope model per issue #8."""

    id: str
    kind: Kind = "person"
    owner_id: str | None = None  # set when kind == "agent"
    display_name: str | None = None
    scopes: tuple[str, ...] = ()  # subset of owner scopes for agents
    auth_level: int = 1  # 1 bearer/session, 2 recent, 3 fresh-2fa
    source: str = "token"  # token | oidc | header | scheduler
    #: The person's role (owner/admin/member/supervised/guest). For an
    #: agent principal this carries its OWNER's role, so ``can()`` can
    #: reason about "the lesser of scopes and the person" without I/O.
    role: str = "member"
    #: True for a read-only viewer credential: it acts as ``id`` (the owning
    #: person) for reads, but the auth layer refuses every write, every
    #: step-up and every route on the viewer deny list (see api.py).
    read_only: bool = False


def is_admin(principal: Principal | None) -> bool:
    """Deprecated thin wrapper — kept for callers not yet migrated.

    New code asks ``can(principal, permission)`` (see roles.py). This
    remains one shared definition of the old gate so the rooms action
    path and anything else still importing it cannot drift: admin in the
    permission model means "may approve", which owner and admin hold.
    """
    return can(principal, "approve")


def role_for_record(record: dict) -> str:
    """The role stored on a person record, with back-compat reads.

    New records carry ``role``. Pre-roles records are read like this:
    the bootstrap ``primary`` is the owner; a legacy ``admin`` scope
    means admin; everything else is a member. Never a guessed role.
    """
    role = record.get("role")
    if isinstance(role, str) and role in ROLES:
        return role
    if record.get("user_id") == BOOTSTRAP_PRINCIPAL_ID:
        return "owner"
    if "admin" in (record.get("scopes") or ()):
        return "admin"
    return "member"


def _token_fingerprint(token: str) -> str:
    """sha256 for high-entropy tokens; constant-time compare upstream."""
    return hashlib.sha256(token.encode()).hexdigest()


def _iso_to_epoch(value: Any) -> float | None:
    """An epoch time from an ISO-8601 string, or ``None`` if unreadable."""
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


def record_is_expired(record: dict | None, now: float | None = None) -> bool:
    """True when a guest record's ``until`` has passed.

    Only a **guest** expires: the check is role-aware, so a person whose
    role has moved on (an ex-guest promoted to member) is never killed by
    a stale ``guest_until`` left on their record. A guest's
    ``guest_until`` must be readable; an unreadable value is treated as
    expired (fail closed) so a corrupt timestamp cannot keep an account
    open.
    """
    if record is None:
        return True
    if role_for_record(record) != "guest":
        return False
    until = record.get("guest_until")
    if not until:
        return False
    expires = _iso_to_epoch(until)
    if expires is None:
        return True
    return expires <= (now if now is not None else time.time())


class NoPrincipalError(Exception):
    """Raised when no token / no matching hashed token is present."""


class IdentityStore:
    """Local users + per-user hashed token records.

    Storage shape (data root):
      users.json       — list of {user_id, display_name, role, scopes?,
                          hashed_tokens, token_prefixes, enabled, created_at}
    Single-writer: the FastAPI process. Read-only for CLI helpers.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "users.json"

    # -- load/save ------------------------------------------------------
    def _load(self) -> dict:
        if not self.path.exists():
            return {"users": []}
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            # Preserve the corrupt file for recovery instead of silently
            # overwriting it on the next _save().  Auth fails closed
            # (empty user list → no tokens match) and the operator gets
            # a visible signal in the log and a .corrupt backup file.
            corrupt_path = self.path.with_suffix(".json.corrupt")
            _logger.warning(
                "users.json corrupt or unreadable (%s); "
                "preserving as %s and starting empty",
                exc,
                corrupt_path,
            )
            try:
                os.replace(self.path, corrupt_path)
            except OSError:
                # If rename fails the corrupt file stays in place; we
                # still return empty to fail closed.
                pass
            return {"users": []}

    def _save(self, payload: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        os.replace(tmp, self.path)

    # -- operations ------------------------------------------------------
    def create_user(
        self,
        user_id: str,
        display_name: str | None,
        initial_plain_token: str | None = None,
        role: str = "member",
        guest_until: str | None = None,
    ) -> dict:
        payload = self._load()
        if any(u.get("user_id") == user_id for u in payload["users"]):
            raise ValueError(f"user exists: {user_id}")
        u = {
            "user_id": user_id,
            "display_name": display_name,
            "role": role if role in ROLES else "member",
            "hashed_tokens": [],
            "token_prefixes": [],
            "enabled": True,
            "created_at": time.time(),
        }
        if guest_until:
            u["guest_until"] = guest_until
        if initial_plain_token:
            self._attach_token(u, initial_plain_token)
        payload["users"].append(u)
        self._save(payload)
        return u

    def set_guest_until(self, user_id: str, guest_until: str) -> dict | None:
        """Set (or clear, with an empty string) a person's guest expiry."""
        payload = self._load()
        for u in payload.get("users", []):
            if u.get("user_id") == user_id:
                if guest_until:
                    u["guest_until"] = guest_until
                else:
                    u.pop("guest_until", None)
                self._save(payload)
                return u
        return None

    def attach_token(self, user_id: str, plain_token: str) -> None:
        payload = self._load()
        for u in payload["users"]:
            if u.get("user_id") == user_id:
                self._attach_token(u, plain_token)
                self._save(payload)
                return
        raise ValueError(f"no such user: {user_id}")

    def attach_hashed_token(self, user_id: str, plain_token: str) -> None:
        """Attach a credential by hash only — no prefix is kept.

        Used for the sign-in key issued when a person accepts an invite.
        That key is *generated*, not chosen by a human: the one caller
        (``api.py``, invite accept) passes ``secrets.token_urlsafe(32)``,
        a 256-bit CSPRNG value. So a single unsalted SHA-256 is the
        right fingerprint for it — a slow KDF would cost matching time
        without adding resistance, because the input is not guessable.
        (This docstring used to claim a human password arrived here; it
        did not. A real password needs ``pbkdf2_hmac``, as ``vault.py``
        does for vault secrets, and must never reach this function.)

        Only the hash is written — deliberately not the ``token_prefixes``
        display hint that ``_attach_token`` records.
        """
        payload = self._load()
        for u in payload["users"]:
            if u.get("user_id") == user_id:
                u.setdefault("hashed_tokens", []).append(
                    _token_fingerprint(plain_token)
                )
                self._save(payload)
                return
        raise ValueError(f"no such user: {user_id}")

    def disable_user(self, user_id: str) -> bool:
        payload = self._load()
        for u in payload["users"]:
            if u.get("user_id") == user_id:
                u["enabled"] = False
                self._save(payload)
                return True
        return False

    def list_users(self) -> list[dict]:
        return self._load().get("users", [])

    # -- roles (owner-approved 2026-09-26) -------------------------------
    def get_user(self, user_id: str) -> dict | None:
        """One enabled-or-disabled person record by id, or ``None``."""
        for u in self._load().get("users", []):
            if u.get("user_id") == user_id:
                return u
        return None

    def role_for(self, user_id: str) -> str | None:
        """The stored (with back-compat) role for a person, or ``None``."""
        rec = self.get_user(user_id)
        return role_for_record(rec) if rec is not None else None

    def set_role(self, user_id: str, role: str) -> dict | None:
        """Write a person's role. Unknown role → ``ValueError`` (fail
        closed); unknown person → ``None``. Never touches agents."""
        if role not in ROLES:
            raise ValueError(f"unknown role: {role!r}")
        payload = self._load()
        for u in payload.get("users", []):
            if u.get("user_id") == user_id:
                u["role"] = role
                # Once a role is written it is the only authority: drop the
                # pre-roles ``admin`` scope, or a demoted admin would stay
                # admin (and migrate_roles would promote them back at boot).
                scopes = [sc for sc in (u.get("scopes") or []) if sc != "admin"]
                if scopes:
                    u["scopes"] = scopes
                else:
                    u.pop("scopes", None)
                self._save(payload)
                return u
        return None

    def owner_id(self) -> str | None:
        """The id of the person whose role is owner, or ``None``.

        Exactly one by design; the first owner found wins (a second can
        only appear through a bug, and the code does not guess which is
        right)."""
        for u in self._load().get("users", []):
            if role_for_record(u) == "owner":
                return u.get("user_id")
        return None

    def migrate_roles(self) -> int:
        """Give pre-roles records their role. Returns how many changed.

        Rules (owner-approved 2026-09-26): ``primary`` → owner; a person
        carrying the legacy ``admin`` scope → admin; everyone else →
        member. Idempotent: a record that already has a role is left
        alone. Called at boot so the store is self-describing; readers
        also fall back through :func:`role_for_record`, so a store that
        has never been migrated still authorizes correctly.
        """
        payload = self._load()
        changed = 0
        for u in payload.get("users", []):
            stored = u.get("role")
            if isinstance(stored, str) and stored in ROLES:
                # Back-compat upgrade: a legacy admin scope outranks a
                # default member role, so the scope and role cannot
                # disagree after migration.
                if "admin" in (u.get("scopes") or ()) and stored == "member":
                    u["role"] = "admin"
                    changed += 1
                continue
            u["role"] = role_for_record(u)
            changed += 1
        if changed:
            self._save(payload)
        return changed

    # -- profile ----------------------------------------------------------
    def get_display_name(self, user_id: str) -> str | None:
        """Stored display name for a person, or None if never set."""
        for u in self._load().get("users", []):
            if u.get("user_id") == user_id:
                return u.get("display_name")
        return None

    def set_display_name(self, user_id: str, display_name: str) -> dict:
        """Upsert a person's display name in private runtime state
        (data/users.json). In single mode the "primary" record is created
        without any token so it can never authenticate by itself."""
        payload = self._load()
        for u in payload["users"]:
            if u.get("user_id") == user_id:
                u["display_name"] = display_name
                self._save(payload)
                return u
        u = {
            "user_id": user_id,
            "display_name": display_name,
            "role": "owner" if user_id == BOOTSTRAP_PRINCIPAL_ID else "member",
            "hashed_tokens": [],
            "token_prefixes": [],
            "enabled": True,
            "created_at": time.time(),
        }
        payload["users"].append(u)
        self._save(payload)
        return u

    def _attach_token(self, user: dict, plain_token: str) -> None:
        user.setdefault("hashed_tokens", []).append(_token_fingerprint(plain_token))
        user.setdefault("token_prefixes", []).append(plain_token[:8])

    # -- resolution -------------------------------------------------------
    def match_token(self, token: str) -> dict | None:
        """Find the enabled user or agent whose hashed token matches."""
        fp = _token_fingerprint(token)
        payload = self._load()
        for u in payload.get("users", []) + payload.get("agents", []):
            if not u.get("enabled", False):
                continue
            if record_is_expired(u):
                # A guest past their `until` resolves to nothing: the
                # credential is not refused with a reason, it never
                # matches (fail closed, same as a disabled account).
                continue
            if any(hmac.compare_digest(fp, h) for h in u.get("hashed_tokens", [])):
                return u
        return None

    def get_principal_record(self, principal_id: str) -> dict | None:
        """Look up an enabled user or agent record by principal id.

        Used by the session/OIDC resolver: a browser session stores the
        resolved principal id, never a raw credential, so re-resolving
        it must go through the same enabled-records store the bearer
        path uses. Disabled records resolve to nothing (fail closed).
        """
        if not principal_id:
            return None
        payload = self._load()
        for u in payload.get("users", []) + payload.get("agents", []):
            if u.get("user_id") == principal_id and u.get("enabled", False):
                if record_is_expired(u):
                    # An expired guest's session resolves to nothing on
                    # the next request, exactly like a disabled account.
                    return None
                return u
        return None

    def find_by_oidc_subject(self, sub: str) -> dict | None:
        """The enabled person whose linked sign-ins include ``sub``."""
        if not sub:
            return None
        for u in self._load().get("users", []):
            if sub in (u.get("oidc_subjects") or []) and u.get("enabled", False):
                return u
        return None

    def link_oidc_subject(self, user_id: str, sub: str) -> dict:
        """Link a verified provider subject to one person's account.

        A subject belongs to at most one person: linking a subject that
        is already linked to someone else raises ``ValueError``. Linking
        it again to the same person is a no-op.
        """
        if not sub:
            raise ValueError("empty subject")
        payload = self._load()
        target = None
        for u in payload.get("users", []):
            subs = u.get("oidc_subjects") or []
            if sub in subs and u.get("user_id") != user_id:
                raise ValueError("subject is linked to another account")
            if u.get("user_id") == user_id and u.get("enabled", False):
                target = u
        if target is None:
            raise ValueError("no such account")
        subs = target.setdefault("oidc_subjects", [])
        if sub not in subs:
            subs.append(sub)
            self._save(payload)
        return target

    # -- agent principals (phase 3) --------------------------------------
    def create_agent(
        self,
        agent_id: str,
        owner_id: str,
        scopes: tuple[str, ...],
        plain_token: str | None = None,
        display_name: str | None = None,
    ) -> dict:
        """An agent is a first-class principal owned by a person.

        Scopes are a subset language from the owner: "read", "write",
        "journal", "apps", "notify". Agents never inherit owner rights
        beyond the listed scopes.
        """
        payload = self._load()
        if any(a.get("user_id") == agent_id for a in payload.get("agents", [])):
            raise ValueError(f"agent exists: {agent_id}")
        a = {
            "user_id": agent_id,
            "kind": "agent",
            "owner_id": owner_id,
            "display_name": display_name or agent_id,
            "scopes": list(scopes),
            "hashed_tokens": [],
            "token_prefixes": [],
            "enabled": True,
            "created_at": time.time(),
        }
        if plain_token:
            self._attach_token(a, plain_token)
        payload.setdefault("agents", []).append(a)
        self._save(payload)
        return a

    def list_agents(self, owner_id: str | None = None) -> list[dict]:
        payload = self._load()
        agents = [a for a in payload.get("agents", []) if a.get("enabled")]
        if owner_id:
            agents = [a for a in agents if a.get("owner_id") == owner_id]
        return agents

    def disable_agent(self, agent_id: str, owner_id: str) -> bool:
        payload = self._load()
        for a in payload.get("agents", []):
            if a.get("user_id") == agent_id and a.get("owner_id") == owner_id:
                a["enabled"] = False
                self._save(payload)
                return True
        return False

    # -- read-only viewer credentials ---------------------------------------
    # Kept in their own list so nothing that walks users/agents (session
    # resolution, listings, login) can ever see or match one.
    def create_viewer(
        self, viewer_id: str, owner_id: str, plain_token: str, label: str = ""
    ) -> dict:
        payload = self._load()
        if any(v.get("user_id") == viewer_id for v in payload.get("viewers", [])):
            raise ValueError(f"viewer exists: {viewer_id}")
        v = {
            "user_id": viewer_id,
            "kind": "viewer",
            "owner_id": owner_id,
            "label": label[:80],
            "hashed_tokens": [],
            "token_prefixes": [],
            "enabled": True,
            "created_at": time.time(),
        }
        self._attach_token(v, plain_token)
        payload.setdefault("viewers", []).append(v)
        self._save(payload)
        return v

    def list_viewers(self, owner_id: str | None = None) -> list[dict]:
        """Enabled viewers, without any hash (public fields only)."""
        out = []
        for v in self._load().get("viewers", []):
            if not v.get("enabled") or (owner_id and v.get("owner_id") != owner_id):
                continue
            out.append(
                {
                    "viewer_id": v["user_id"],
                    "owner_id": v.get("owner_id"),
                    "label": v.get("label", ""),
                    "token_prefix": (v.get("token_prefixes") or [""])[0],
                    "created_at": v.get("created_at"),
                }
            )
        return out

    def disable_viewer(self, viewer_id: str, owner_id: str) -> bool:
        payload = self._load()
        for v in payload.get("viewers", []):
            if (
                v.get("user_id") == viewer_id
                and v.get("owner_id") == owner_id
                and v.get("enabled")
            ):
                v["enabled"] = False
                self._save(payload)
                return True
        return False

    def match_viewer(self, token: str) -> dict | None:
        fp = _token_fingerprint(token)
        for v in self._load().get("viewers", []):
            if v.get("enabled") and any(
                hmac.compare_digest(fp, h) for h in v.get("hashed_tokens", [])
            ):
                return v
        return None

    def legacy_primary(self, instance_token: str) -> dict:
        """The bootstrap person in single mode (id "primary")."""
        payload = self._load()
        users = payload.get("users", [])
        for u in users:
            if u.get("user_id") == BOOTSTRAP_PRINCIPAL_ID:
                if not u.get("hashed_tokens"):
                    # record created tokenless (e.g. display-name set in
                    # single mode) — attach the instance credential so a
                    # mode switch never locks the owner out.
                    self._attach_token(u, instance_token)
                    self._save(payload)
                if not u.get("role"):
                    # A primary record made before roles existed is the
                    # owner; heal it in place so it is self-describing.
                    u["role"] = "owner"
                    self._save(payload)
                return u
        return self.create_user(
            BOOTSTRAP_PRINCIPAL_ID,
            "Primary person",
            initial_plain_token=instance_token,
            role="owner",
        )


DEV_BYPASS_ENV = "PW_DEV_AUTH_BYPASS"


def dev_bypass_enabled() -> bool:
    """Temporary local-development ergonomics (loopback-only).

    Explicit opt-in via PW_DEV_AUTH_BYPASS=1. Default OFF; when off,
    nothing about auth changes. See api.py for the loopback-only gate
    that consumes this flag.
    """
    return os.environ.get(DEV_BYPASS_ENV, "").strip() in ("1", "true", "yes")


def dev_bypass_principal() -> Principal:
    """The principal the dev bypass resolves to: the bootstrap primary
    person, visibly marked with its own auth source."""
    return Principal(
        id=BOOTSTRAP_PRINCIPAL_ID,
        kind="person",
        display_name="Primary person",
        auth_level=1,
        source="dev-bypass",
        role="owner",
    )


def _owner_role(store: IdentityStore | None, record: dict) -> str:
    """The role of an agent record's owner, for "the lesser of" checks.

    Falls back to ``member`` (least privilege that still owns a space)
    when the owner cannot be found — never to owner/admin.
    """
    if store is None or record.get("kind") != "agent":
        return "member"
    owner = store.get_user(record.get("owner_id") or "")
    return role_for_record(owner) if owner is not None else "member"


def principal_from_record(
    record: dict, source: str = "token", store: IdentityStore | None = None
) -> Principal:
    """Canonical record → Principal. Agents keep owner_id and scopes;
    persons carry their stored display name and role. Session and OIDC
    resolution reuse this so every credential path lands on the same
    Principal shape."""
    if record.get("kind") == "agent":
        return Principal(
            id=record["user_id"],
            kind="agent",
            owner_id=record.get("owner_id"),
            display_name=record.get("display_name"),
            scopes=tuple(record.get("scopes") or ()),
            auth_level=1,
            source=source,
            # An agent's role is its owner's: the permission half of the
            # "lesser of scopes and the person" rule.
            role=_owner_role(store, record),
        )
    return Principal(
        id=record["user_id"],
        kind="person",
        display_name=record.get("display_name"),
        auth_level=1,
        source=source,
        role=role_for_record(record),
    )


def resolve_principal(
    token: str | None,
    store: IdentityStore | None,
    mode: str,
    instance_token: str | None,
    *,
    allow_read_only: bool = False,
) -> Principal:
    """The single entry point. No handler ever sees the raw token.

    A read-only viewer credential resolves only when the caller passes
    ``allow_read_only=True`` (the API's bearer path does). Login, step-up
    and the CLI never do, so a viewer token can not be traded for a
    session, an elevation or an approval."""
    # A project's learning key (PW_LEARNING_TOKEN), in either mode: an agent
    # of the primary person whose only scope is "learning"; api.py confines
    # it to /api/learning (CONFINING_SCOPES). It never becomes the person.
    learning_token = os.environ.get("PW_LEARNING_TOKEN", "")
    if learning_token and token and hmac.compare_digest(token, learning_token):
        return Principal(
            id="learning-key",
            kind="agent",
            owner_id=BOOTSTRAP_PRINCIPAL_ID,
            display_name="A project's learning key",
            scopes=("learning",),
            auth_level=1,
            source="token",
            role="owner",
        )
    # An app's sticker key (PW_STICKERS_TOKENS="app=token,app=token"): an
    # agent of the primary person that may only report its own app's
    # stickers (api.py confines "stickers" to /api/stickers/found).
    for pair in os.environ.get("PW_STICKERS_TOKENS", "").split(","):
        app_id, _, value = pair.strip().partition("=")
        app_id, value = app_id.strip(), value.strip()
        if app_id and value and token and hmac.compare_digest(token, value):
            return Principal(
                id=f"stickers-{app_id}",
                kind="agent",
                owner_id=BOOTSTRAP_PRINCIPAL_ID,
                display_name=f"{app_id}'s sticker key",
                scopes=("stickers",),
                auth_level=1,
                source="token",
                role="owner",
            )
    if store is not None and token:
        viewer = store.match_viewer(token)
        if viewer is not None:
            if not allow_read_only:
                raise NoPrincipalError("read-only credential not accepted here")
            owner_id = viewer.get("owner_id") or ""
            owner = store.get_user(owner_id)
            if owner is not None:
                if not owner.get("enabled", True) or record_is_expired(owner):
                    raise NoPrincipalError("viewer's owner is not active")
                role = role_for_record(owner)
            elif mode == "multi" or owner_id != BOOTSTRAP_PRINCIPAL_ID:
                raise NoPrincipalError("viewer's owner not found")
            else:
                role = "owner"
            return Principal(
                id=owner_id,
                kind="person",
                display_name=(owner or {}).get("display_name") or "Primary person",
                auth_level=1,
                source="viewer",
                role=role,
                read_only=True,
            )
    if mode == "multi" and store is not None:
        found = store.match_token(token or "")
        if not found:
            raise NoPrincipalError("no principal for token")
        return principal_from_record(found, source="token", store=store)
    # single mode: the instance token remains the only way to become the
    # primary person, but an agent token (POST /api/identity/agents works
    # in single mode too, scoped under the primary owner) must still
    # resolve -- otherwise a credential the API happily mints can never
    # authenticate anything. Only "agent" records match here; a "user"
    # record never does, so single-mode person resolution stays exactly
    # the legacy single-token gate the module docstring promises.
    if store is not None and token:
        found = store.match_token(token)
        if found is not None and found.get("kind") == "agent":
            return principal_from_record(found, source="token", store=store)
    if (
        not instance_token
        or not token
        or not hmac.compare_digest(token, instance_token)
    ):
        raise NoPrincipalError()
    return Principal(
        id=BOOTSTRAP_PRINCIPAL_ID,
        kind="person",
        display_name="Primary person",
        auth_level=1,
        source="token",
        role="owner",
    )


def resolve_session_principal(
    session_principal_id: str | None,
    store: IdentityStore | None,
    mode: str,
    auth_method: str = "local",
) -> Principal:
    """Resolve a browser session through the same canonical entry point.

    A session stores only the id of the principal it was created for;
    it carries no credential. Resolution therefore re-reads the current
    enabled record (multi mode) so disabling a user revokes their
    browser session on the next request, exactly like their bearer
    token. Single mode resolves every in-app login to the bootstrap
    "primary" person — the one person that install has.
    """
    source = "oidc" if auth_method == "oidc" else "session"
    if mode == "multi" and store is not None:
        record = store.get_principal_record(session_principal_id or "")
        if record is None:
            raise NoPrincipalError("no principal for session")
        return principal_from_record(record, source=source, store=store)
    if not session_principal_id:
        raise NoPrincipalError("empty session principal")
    return Principal(
        id=BOOTSTRAP_PRINCIPAL_ID,
        kind="person",
        display_name="Primary person",
        auth_level=1,
        source=source,
        role="owner",
    )


def resolve_oidc_principal(
    sub: str | None,
    store: IdentityStore | None,
    mode: str,
    display_name: str | None = None,
) -> Principal:
    """Map a verified OIDC identity onto a local principal.

    Single mode has exactly one person, so a verified external identity
    resolves to the bootstrap primary person (OIDC is an alternate
    sign-in for the owner). Multi mode requires an existing enabled
    local record whose id matches the provider subject (or the display
    fallback); an unmapped identity resolves to nothing so external
    sign-in can never silently mint an account. Fail closed.
    """
    if mode == "multi" and store is not None:
        linked = store.find_by_oidc_subject(sub or "")
        if linked is not None:
            return principal_from_record(linked, source="oidc", store=store)
        for candidate in (sub, display_name):
            record = store.get_principal_record(candidate or "")
            if record is not None:
                return principal_from_record(record, source="oidc", store=store)
        raise NoPrincipalError("oidc identity has no local account")
    if not sub:
        raise NoPrincipalError("empty oidc subject")
    return Principal(
        id=BOOTSTRAP_PRINCIPAL_ID,
        kind="person",
        display_name="Primary person",
        auth_level=1,
        source="oidc",
        role="owner",
    )


def apply_group_role(
    store: IdentityStore | None,
    principal: Principal,
    groups: tuple[str, ...] | list[str] | None,
    mapping: str | None,
) -> Principal:
    """Map OIDC ``groups`` to a role and store it on the person.

    Reads (never invents) the role from ``mapping`` (``PW_ROLE_GROUPS``);
    a person with no matching group keeps their stored role, as do local
    (non-SSO) accounts. **The owner is never demoted**: if the stored role
    is owner the sign-in changes nothing. Returns the (possibly updated)
    principal so the caller's session resolves on the fresh role.
    """
    if store is None or principal.kind != "person" or not groups or not mapping:
        return principal
    role = role_for_groups(list(groups), mapping)
    if role is None:
        return principal
    current = store.get_user(principal.id)
    if current is None:
        # No local record to update (single-mode primary, typically):
        # leave the owner/principal exactly as resolved.
        return principal
    if role_for_record(current) == "owner":
        return principal
    store.set_role(principal.id, role)
    fresh = store.get_principal_record(principal.id)
    return (
        principal_from_record(fresh, source=principal.source, store=store)
        if fresh is not None
        else principal
    )


# ── Per-user data paths (product decision #13: multi-user) ─────────────
#
# One instance can serve several people. Per-user state resolves through
# ONE helper — principal_scoped_path() — so every store (world, journal,
# reminders, proposals, chat history, interests) partitions the same way
# and no handler invents its own layout.
#
# Boundary (see docs/IDENTITY-BOUNDARY.md):
#   per-user — world (incl. prefs + sections/map layout), journal,
#              reminders, proposals, chat history, interests
#   global   — runtime/app config, capability catalog, system health,
#              deployment config, shared connections registry
#
# Legacy mapping (no silent migration loss): in single mode — the
# default — every kind resolves to the SAME instance-level path current
# installs already use (world.json, journal.ndjson, reminders.json,
# proposals.json under the data dir; discovery.json under ~/.config).
# A multi-mode install is an explicit opt-in: each person (and each
# agent, via its owner) gets data/users/<id>/<file>.

#: Per-user state kinds and their file names inside a user tree.
SCOPED_PATH_FILENAMES: dict[str, str] = {
    "world": "world.json",
    "journal": "journal.ndjson",
    "reminders": "reminders.json",
    "proposals": "proposals.json",
    "chat_history": "chat-history.ndjson",
    # lining rescue (D15): journal drafts must survive devices; registered
    # like every other kind so single/multi mode resolve identically.
    "journal_draft": "journal-draft.json",
    # edit-pair capture v0 (B5, DRAFT-SYNC-SPEC §capture lineage): one
    # BOT→Rylee edit pair per NDJSON line, per principal, same entry point.
    "journal_edit_pairs": "journal-edit-pairs.ndjson",
    # Briefing continuity: where the person last was, so a later visit
    # can say "arrived while you were away". Same per-principal entry point as
    # drafts; the briefing contract (worlds-briefing/1) owns the shape.
    "last_place": "last-place.json",
    # Rooms visit state: which room the person last visited and which of
    # its needs they have already marked seen (Worlds-owned, private,
    # never sent to a room). Same per-principal entry point as drafts/place.
    "rooms_visits": "rooms-visits.json",
    # Book Girl (owner, 2026-09-27): which ideas this person has met, where
    # they first met them, and how they like to be taught. Private,
    # never sent to a room or a model; the person's own learning memory.
    "learning": "learning.json",
    # The sticker album (stickers/0): what this person found, and where it sits.
    "stickers": "stickers.json",
    # Pollen's Later shelf (owner, 2026-09-27): ideas kept safe for later,
    # at most three in progress at once. Private to the person.
    "later": "later.json",
    # Crew registry (owner decision 2026-09-25): the person's own
    # companions and which of them keeps which room. Worlds-owned,
    # private, never sent to a room or a model. Same per-principal entry point
    # as drafts/place; uploaded portrait bytes are files under a sibling
    # directory of this file (crew.portrait_dir), not a new store.
    "crew": "crew.json",
    # Web Push (native notifications, 2026-09-26): the devices a person
    # turned push on for, and their notification history + prefs. Both
    # are per-person state; the endpoint/keys a subscription record
    # carries are credentials and never leave the store toward a
    # response. See docs/NOTIFICATIONS.md.
    "push_subscriptions": "push-subscriptions.json",
    "notifications": "notifications.json",
    # Journal gate denylist (owner design, 2026-09-27): topics/agents the
    # gate must always answer "unsure" about, checked before retrieval
    # or any model call. Private to the person; never sent to a room.
    "journal_gate_denylist": "journal-gate-denylist.json",
}

_SAFE_PRINCIPAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def legacy_scoped_path(data_dir: Path | str, kind: str) -> Path:
    """The instance-level path a kind has always used (single mode)."""
    if kind not in SCOPED_PATH_FILENAMES:
        raise ValueError(f"unknown scoped path kind: {kind!r}")
    return Path(data_dir) / SCOPED_PATH_FILENAMES[kind]


def principal_scoped_path(
    data_dir: Path | str,
    principal: Principal | None,
    kind: str,
    *,
    mode: str = "single",
) -> Path:
    """Resolve one per-user state kind to a concrete file path.

    Rules (in order):
    - unknown kind → ValueError (fail closed, never a guessed path)
    - single mode, or no principal (background/scheduler entry points) →
      the legacy instance path, byte-identical to today's behavior
    - multi mode → data/users/<id>/<file>, where <id> is the person's
      id, or an agent's OWNER id (agents act on their owner's tree, so
      an agent-proposed reminder lands where the owner will review it)
    - an id that is not a safe path segment → ValueError (no traversal)
    """
    if kind not in SCOPED_PATH_FILENAMES:
        raise ValueError(f"unknown scoped path kind: {kind!r}")
    if mode != "multi" or principal is None:
        return legacy_scoped_path(data_dir, kind)
    tree_id = principal.id
    if principal.kind == "agent" and principal.owner_id:
        tree_id = principal.owner_id
    if not _SAFE_PRINCIPAL_ID.match(tree_id or ""):
        raise ValueError(f"principal id is not a safe path segment: {tree_id!r}")
    return Path(data_dir) / "users" / tree_id / SCOPED_PATH_FILENAMES[kind]
