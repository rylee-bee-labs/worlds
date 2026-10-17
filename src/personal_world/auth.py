"""Native auth: provider-neutral OIDC + local bootstrap.

Project Worlds owns identity mapping, browser sessions, authorization,
step-up requirements, and session expiry. External OIDC providers
(Authelia, future providers) authenticate identity; Worlds owns the session.
"""

import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_logger = logging.getLogger("personal_world.auth")


@dataclass
class Session:
    """A browser session."""

    id: str
    principal_id: str
    created_at: float
    last_active: float
    step_up_until: float | None = None
    step_up_principal: str | None = None
    auth_method: str = "local"  # "local" or "oidc"

    def is_valid(self, max_age: int = 86400) -> bool:
        return (time.time() - self.last_active) < max_age

    def has_step_up(self, principal_id: str | None = None) -> bool:
        """A live, time-bounded elevation for this session.

        When ``principal_id`` is supplied the elevation must have been
        granted to that same principal: an elevation can never be spent
        by a different identity that somehow shares the cookie.
        """
        if self.step_up_until is None or time.time() >= self.step_up_until:
            return False
        if principal_id is not None and self.step_up_principal != principal_id:
            return False
        return True

    def touch(self):
        self.last_active = time.time()


@dataclass
class OIDCConfig:
    """OIDC provider configuration."""

    issuer: str
    client_id: str
    client_secret_env: str  # env var name, not the value
    scopes: list[str] = field(default_factory=lambda: ["openid", "profile"])
    display_name: str = "SSO"

    @property
    def authorization_endpoint(self) -> str:
        return f"{self.issuer}/api/oidc/authorization"

    @property
    def token_endpoint(self) -> str:
        return f"{self.issuer}/api/oidc/token"

    @property
    def userinfo_endpoint(self) -> str:
        return f"{self.issuer}/api/oidc/userinfo"


class SessionStore:
    """Server-side session storage."""

    def __init__(self, data_dir: Path):
        self._sessions: dict[str, Session] = {}
        self._data_dir = data_dir
        self._load()

    def create(self, principal_id: str, auth_method: str = "local") -> Session:
        session = Session(
            id=secrets.token_urlsafe(32),
            principal_id=principal_id,
            created_at=time.time(),
            last_active=time.time(),
            auth_method=auth_method,
        )
        self._sessions[session.id] = session
        self._save()
        return session

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session and session.is_valid():
            session.touch()
            return session
        if session:
            del self._sessions[session_id]
            self._save()
        return None

    def invalidate(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._save()

    def grant_step_up(
        self, session_id: str, principal_id: str | None = None, duration: int = 300
    ) -> Session | None:
        """Mint a time-bounded elevation for a session.

        The elevation is bound to the session's own principal. If a
        ``principal_id`` is supplied it must match — an elevation is
        never issued across identities.
        """
        session = self.get(session_id)
        if session is None:
            return None
        if principal_id is not None and session.principal_id != principal_id:
            return None
        session.step_up_until = time.time() + duration
        session.step_up_principal = session.principal_id
        self._save()
        return session

    def _load(self):
        path = self._data_dir / "sessions.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                for sid, s in data.items():
                    self._sessions[sid] = Session(**s)
            except Exception as exc:
                # Never silent: sessions.json being unreadable must be
                # visible in logs (everyone is logged out, which is a
                # real event the owner may need to diagnose).
                _logger.warning(
                    "sessions file unreadable; starting with no sessions: %s", exc
                )

    def _save(self):
        """Atomic 0600 write: tmp file + os.replace — a crash or a
        concurrent reader never observes a half-written session file,
        and the credential store is never world-readable."""
        path = self._data_dir / "sessions.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            sid: {
                "id": s.id,
                "principal_id": s.principal_id,
                "created_at": s.created_at,
                "last_active": s.last_active,
                "step_up_until": s.step_up_until,
                "step_up_principal": s.step_up_principal,
                "auth_method": s.auth_method,
            }
            for sid, s in self._sessions.items()
        }
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass  # best-effort hardening under restrictive umask policy
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


class AuthManager:
    """Manages authentication flows.

    Every successful login resolves a canonical ``Principal`` through
    ``identity.py`` first; the session stores only that principal's id.
    That makes a browser session a first-class credential on the same
    entry point as a bearer token rather than a parallel credential system.
    """

    def __init__(self, data_dir: Path, config_dir: Path, identity: dict | None = None):
        self.sessions = SessionStore(data_dir)
        self._config_dir = config_dir
        self._oidc_config: OIDCConfig | None = None
        self._bootstrap_token: str | None = None
        # The app's identity entry point state ({mode, store, instance_token}),
        # used to resolve local/browser/OIDC logins onto the same
        # Principal the bearer path produces. Optional so direct
        # construction (tests, tooling) still works.
        self._identity = identity
        self._load_config()

    def _load_config(self):
        oidc_path = self._config_dir / "oidc.json"
        if oidc_path.exists():
            try:
                data = json.loads(oidc_path.read_text())
                self._oidc_config = OIDCConfig(**data)
            except Exception:  # nosec B110  # unreadable OIDC config means OIDC is simply off
                pass
        self._bootstrap_token = os.environ.get("PW_API_TOKEN")

    def _seam(self) -> tuple[Any, str, str | None]:
        ident = self._identity or {}
        # The app captured the instance token at boot; if that was None
        # (first-run setup creates the token in-process) fall back to the
        # live env so login never lags behind boot-token reconciliation.
        instance_token = ident.get("instance_token") or os.environ.get("PW_API_TOKEN")
        return (ident.get("store"), ident.get("mode", "single"), instance_token)

    def login_local(self, token: str) -> Session | None:
        """Login with the instance/bootstrap credential.

        Resolved through the identity entry point so a browser session lands on
        the same Principal as a bearer request (in multi mode this is
        the user that owns the token, not a fixed string).
        """
        from .identity import NoPrincipalError, resolve_principal

        if self._identity is not None:
            store, mode, instance_token = self._seam()
            try:
                principal = resolve_principal(token, store, mode, instance_token)
            except NoPrincipalError:
                return None
            return self.sessions.create(principal.id, "local")
        # No entry point wired (direct construction): legacy bootstrap compare.
        if self._bootstrap_token and secrets.compare_digest(
            token, self._bootstrap_token
        ):
            return self.sessions.create("primary", "local")
        return None

    def get_oidc_config(self) -> OIDCConfig | None:
        return self._oidc_config

    def login_oidc(
        self,
        sub: str,
        display_name: str | None = None,
        groups: tuple[str, ...] | list[str] | None = None,
    ) -> Session:
        """Login after OIDC callback verification.

        The verified subject is mapped onto a local principal through
        the same entry point. Single mode maps to the bootstrap primary person;
        multi mode requires an existing enabled local record and raises
        ``NoPrincipalError`` otherwise (an unknown IdP identity never
        silently creates an account).

        When the provider asserted ``groups`` and ``PW_ROLE_GROUPS`` is
        set, the person's stored role is updated from the mapping — the
        owner is never demoted. A local account (no groups) keeps its
        stored role.
        """
        from .identity import apply_group_role, resolve_oidc_principal

        store, mode, _ = self._seam()
        principal = resolve_oidc_principal(sub, store, mode, display_name=display_name)
        principal = apply_group_role(
            store, principal, groups, os.environ.get("PW_ROLE_GROUPS", "").strip()
        )
        return self.sessions.create(principal.id, "oidc")

    def grant_oidc_step_up(
        self, session_id: str, sub: str, auth_time: float | None, now: float
    ) -> Session | None:
        """Step-up after a fresh provider sign-in ("Confirm it's you").

        Granted only when the verified subject resolves to the session's
        own principal and the provider says the person signed in within
        the last two minutes (``auth_time``); otherwise ``None``.
        """
        session = self.sessions.get(session_id)
        if session is None or not sub:
            return None
        if auth_time is None or not (now - 120 <= auth_time <= now + 30):
            return None
        from .identity import NoPrincipalError, resolve_oidc_principal

        store, mode, _ = self._seam()
        try:
            principal = resolve_oidc_principal(sub, store, mode)
        except NoPrincipalError:
            return None
        if principal.id != session.principal_id:
            return None
        return self.sessions.grant_step_up(
            session_id, principal_id=session.principal_id, duration=300
        )

    def step_up_methods(self, principal_id: str) -> list[str]:
        """Which ways this person can confirm it's them, for the UI."""
        store, mode, _ = self._seam()
        record = store.get_user(principal_id) if store is not None else None
        methods: list[str] = []
        if principal_id == "primary" or (record and record.get("hashed_tokens")):
            methods.append("key")
        if self.get_oidc_config() is not None and (
            mode != "multi" or (record and record.get("oidc_subjects"))
        ):
            methods.append("sso")
        return methods

    def link_oidc(self, principal_id: str, sub: str) -> None:
        """Link a verified provider subject to a local person (multi mode).

        In single mode every verified sign-in is already the owner, so
        there is nothing to record.
        """
        store, mode, instance_token = self._seam()
        if mode != "multi" or store is None:
            return
        if principal_id == "primary" and instance_token:
            # The bootstrap owner may not have a stored record yet.
            store.legacy_primary(instance_token)
        store.link_oidc_subject(principal_id, sub)

    def validate_session(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def logout(self, session_id: str) -> None:
        self.sessions.invalidate(session_id)

    def verify_step_up_credential(self, session: Session, token: str | None) -> bool:
        """Verify a credential presented for step-up.

        The presented credential is resolved through the canonical entry point
        and must belong to the same principal the session was created
        for. This is the credential event that makes step-up a fresh
        elevation rather than a bare flag.
        """
        if not token:
            return False
        from .identity import NoPrincipalError, resolve_principal

        if self._identity is not None:
            store, mode, instance_token = self._seam()
            try:
                principal = resolve_principal(token, store, mode, instance_token)
            except NoPrincipalError:
                return False
            return principal.id == session.principal_id
        if self._bootstrap_token and secrets.compare_digest(
            token, self._bootstrap_token
        ):
            return session.principal_id == "primary"
        return False

    def request_step_up(
        self, session_id: str, credential: str | None = None
    ) -> Session | None:
        """Elevate a session for a bounded window after re-authentication.

        Returns None when the session is unknown or when the credential
        does not belong to the session's principal. The elevation is
        time-bounded (default 300s) and principal-bound.
        """
        session = self.sessions.get(session_id)
        if session is None:
            return None
        if not self.verify_step_up_credential(session, credential):
            return None
        return self.sessions.grant_step_up(
            session_id, principal_id=session.principal_id, duration=300
        )
