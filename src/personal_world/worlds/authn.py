"""Single-owner authentication for Worlds: sessions, agent tokens, CSRF, fail-closed principals.

Model (see docs/rebuild/CONTRACTS.md C3):

* One human owner. A browser session is a random 256-bit id in an HttpOnly cookie; only
  ``sha256(id)`` is stored (a stolen database cannot be replayed). Sessions have an idle and an
  absolute lifetime, and a ``step_up_at`` stamp set only by a fresh re-authentication.
* Agents use bearer tokens with scopes. Only a hash is stored. **A token is never approval**:
  it can identify a caller, never confirm an action (that needs an owner session with step-up).
* CSRF (cookie auth only): a mutating request must carry an allowed ``Origin`` (no Origin means
  refusal) AND an ``X-CSRF-Token`` header equal to the ``pw_csrf`` cookie AND to the value
  derived from the session. Bearer-token requests carry no ambient credential and skip CSRF.
* Everything fails closed: any unexpected error while authenticating is a 401, never a pass.
* There is no development bypass in this module.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from fastapi import HTTPException, Request

from .db import Database, register_migrations

SESSION_COOKIE = "pw_session"
CSRF_COOKIE = "pw_csrf"
CSRF_HEADER = "x-csrf-token"
IDLE_SECONDS = 12 * 3600
ABSOLUTE_SECONDS = 7 * 24 * 3600
STEP_UP_SECONDS = 300
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

register_migrations("authn", [
    (1, """CREATE TABLE sessions (
        id_hash TEXT PRIMARY KEY, principal TEXT NOT NULL, method TEXT NOT NULL,
        created_at REAL NOT NULL, last_seen_at REAL NOT NULL, expires_at REAL NOT NULL, step_up_at REAL);
CREATE TABLE agent_tokens (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL, scopes TEXT NOT NULL,
        created_at REAL NOT NULL, expires_at REAL, revoked_at REAL, last_used_at REAL)"""),
    (2, """ALTER TABLE sessions ADD COLUMN binding TEXT NOT NULL DEFAULT '';
CREATE TABLE owner_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"""),
])


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Principal:
    kind: str  # "owner" | "agent"
    id: str
    scopes: tuple[str, ...] = ()
    session_hash: str | None = None
    step_up_at: float | None = None
    via: str = "session"  # "session" | "token"

    @property
    def is_owner(self) -> bool:
        return self.kind == "owner"

    def has_step_up(self, now: float | None = None, max_age: int = STEP_UP_SECONDS) -> bool:
        if not self.is_owner or self.via != "session" or self.step_up_at is None:
            return False
        return (now if now is not None else time.time()) - self.step_up_at <= max_age

    def allows_scope(self, scope: str) -> bool:
        """Owner may do anything in scope terms; an agent only what a granted scope covers."""
        if self.is_owner:
            return True
        for granted in self.scopes:
            if granted == scope or (granted.endswith(".*") and scope.startswith(granted[:-1])) or granted == "*":
                return True
        return False


class SessionStore:
    """Sessions are bound to the owner identity (``binding``): when owner.yaml's issuer/subject change,
    every older session stops working."""

    def __init__(self, db: Database, *, clock: Callable[[], float] = time.time,
                 binding: Callable[[], str] = lambda: ""):
        self._db, self._clock, self._binding = db, clock, binding

    def create(self, principal: str = "owner", method: str = "oidc") -> str:
        sid = secrets.token_urlsafe(32)
        now = self._clock()
        with self._db.write_tx() as tx:
            tx.execute("INSERT INTO sessions(id_hash,principal,method,created_at,last_seen_at,expires_at,step_up_at,binding) "
                       "VALUES (?,?,?,?,?,?,?,?)",
                       (_h(sid), principal, method, now, now, now + ABSOLUTE_SECONDS, None, self._binding()))
        return sid

    def get(self, sid: str | None) -> dict | None:
        if not sid or len(sid) > 200:
            return None
        row = self._db.conn().execute("SELECT * FROM sessions WHERE id_hash=?", (_h(sid),)).fetchone()
        if row is None:
            return None
        now = self._clock()
        if now >= row["expires_at"] or now - row["last_seen_at"] > IDLE_SECONDS or row["binding"] != self._binding():
            self.invalidate(sid)
            return None
        if now - row["last_seen_at"] > 60:
            with self._db.write_tx() as tx:
                tx.execute("UPDATE sessions SET last_seen_at=? WHERE id_hash=?", (now, row["id_hash"]))
        return dict(row)

    def mark_step_up(self, sid: str) -> bool:
        with self._db.write_tx() as tx:
            cur = tx.execute("UPDATE sessions SET step_up_at=? WHERE id_hash=?", (self._clock(), _h(sid)))
        return cur.rowcount == 1

    def invalidate(self, sid: str) -> None:
        with self._db.write_tx() as tx:
            tx.execute("DELETE FROM sessions WHERE id_hash=?", (_h(sid),))

    def invalidate_all(self) -> None:
        with self._db.write_tx() as tx:
            tx.execute("DELETE FROM sessions")


class AgentTokenStore:
    PREFIX = "pwa"

    def __init__(self, db: Database, *, clock: Callable[[], float] = time.time):
        self._db, self._clock = db, clock

    def create(self, name: str, scopes: Iterable[str], *, ttl_s: int | None = None) -> tuple[str, str]:
        """Return (token_id, token). The token is shown once; only its hash is kept."""
        tid, secret = secrets.token_hex(6), secrets.token_urlsafe(32)
        token = f"{self.PREFIX}_{tid}_{secret}"
        now = self._clock()
        with self._db.write_tx() as tx:
            tx.execute("INSERT INTO agent_tokens(id,name,token_hash,scopes,created_at,expires_at) VALUES (?,?,?,?,?,?)",
                       (tid, name, _h(token), json.dumps(sorted(set(scopes))), now, now + ttl_s if ttl_s else None))
        return tid, token

    def verify(self, token: str | None) -> Principal | None:
        if not token or len(token) > 300 or not token.startswith(self.PREFIX + "_"):
            return None
        parts = token.split("_", 2)
        if len(parts) != 3:
            return None
        row = self._db.conn().execute("SELECT * FROM agent_tokens WHERE id=?", (parts[1],)).fetchone()
        # Compare against a dummy when the id is unknown so timing does not reveal valid ids.
        expected = row["token_hash"] if row else _h("x" * 8)
        good = hmac.compare_digest(_h(token), expected)
        if row is None or not good or row["revoked_at"] is not None:
            return None
        if row["expires_at"] is not None and self._clock() >= row["expires_at"]:
            return None
        return Principal("agent", row["id"], tuple(json.loads(row["scopes"])), via="token")

    def revoke(self, token_id: str) -> bool:
        with self._db.write_tx() as tx:
            cur = tx.execute("UPDATE agent_tokens SET revoked_at=? WHERE id=? AND revoked_at IS NULL", (self._clock(), token_id))
        return cur.rowcount == 1


def load_csrf_key(data_dir: str | os.PathLike[str]) -> bytes:
    return load_key(data_dir, "csrf.key")


def load_key(data_dir: str | os.PathLike[str], name: str) -> bytes:
    """A persisted random 32-byte key (0600) so every worker process and every restart agrees on it.

    Safe when several processes start at once: the key is written to a uniquely named private file and
    published with ``link`` (atomic, fails with EEXIST if somebody else got there first); the loser
    reads the winner's key. There is no shared temporary name, and no reader ever sees a partial key.
    """
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / name
    for _ in range(50):
        existing = _read_key(path)
        if existing is not None:
            return existing
        key = secrets.token_bytes(32)
        tmp = directory / f".{name}.{secrets.token_hex(8)}.new"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(key)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(tmp, path)          # atomic publish; EEXIST means another process won
                return key
            except FileExistsError:
                continue                    # read the winner's key on the next pass
            except OSError:
                # a filesystem without hard links: exclusive create, and readers wait for the full key
                try:
                    fd2 = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    continue
                with os.fdopen(fd2, "wb") as handle:
                    handle.write(key)
                    handle.flush()
                    os.fsync(handle.fileno())
                return key
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
    raise RuntimeError(f"could not create or read {name}")


def _read_key(path: Path) -> bytes | None:
    """The key if the file holds a complete one; a file still being written is waited for briefly."""
    for _ in range(20):
        try:
            key = path.read_bytes()
        except FileNotFoundError:
            return None
        if len(key) >= 32:
            return key[:32] if len(key) == 32 else key
        time.sleep(0.05)
    raise RuntimeError(f"{path.name} exists but is not a complete key")


@dataclass
class Auth:
    """Everything the routes need to authenticate a request. Build once at startup."""

    db: Database
    csrf_key: bytes
    allowed_origins: frozenset[str]
    clock: Callable[[], float] = time.time
    binding: Callable[[], str] = lambda: ""
    sessions: SessionStore = field(init=False)
    tokens: AgentTokenStore = field(init=False)

    def __post_init__(self):
        self.sessions = SessionStore(self.db, clock=self.clock, binding=self.binding)
        self.tokens = AgentTokenStore(self.db, clock=self.clock)

    def get_state(self, key: str) -> str | None:
        row = self.db.conn().execute("SELECT value FROM owner_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_state(self, key: str, value: str) -> None:
        with self.db.write_tx() as tx:
            tx.execute("INSERT INTO owner_state(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def csrf_token(self, session_id: str) -> str:
        return hmac.new(self.csrf_key, session_id.encode(), hashlib.sha256).hexdigest()

    def authenticate(self, request: Request) -> Principal:
        """Return the caller or raise 401/403. Never returns a principal on an error path."""
        try:
            return self._authenticate(request)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="unauthorized") from None

    def _authenticate(self, request: Request) -> Principal:
        header = request.headers.get("authorization")
        if header is not None:
            scheme, _, value = header.partition(" ")
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="unauthorized")
            principal = self.tokens.verify(value.strip())
            if principal is None:
                raise HTTPException(status_code=401, detail="unauthorized")
            return principal
        sid = request.cookies.get(SESSION_COOKIE)
        row = self.sessions.get(sid)
        if row is None:
            raise HTTPException(status_code=401, detail="unauthorized")
        if request.method in MUTATING or request.method not in ("GET", "HEAD", "OPTIONS"):
            self._check_csrf(request, sid)
        return Principal("owner", row["principal"], session_hash=row["id_hash"],
                         step_up_at=row["step_up_at"], via="session")

    def _check_csrf(self, request: Request, sid: str) -> None:
        origin = request.headers.get("origin")
        if origin is None or origin.rstrip("/") not in self.allowed_origins:
            raise HTTPException(status_code=403, detail="origin not allowed")
        header = request.headers.get(CSRF_HEADER, "")
        cookie = request.cookies.get(CSRF_COOKIE, "")
        expected = self.csrf_token(sid)
        if not (header and cookie and hmac.compare_digest(header, cookie) and hmac.compare_digest(header, expected)):
            raise HTTPException(status_code=403, detail="csrf check failed")


def principal_dependency(auth: Auth, *, owner_only: bool = True):
    """FastAPI dependency: the caller, or 401/403. ``owner_only`` rejects agent tokens (403)."""

    def dep(request: Request) -> Principal:
        principal = auth.authenticate(request)
        if owner_only and not principal.is_owner:
            raise HTTPException(status_code=403, detail="owner only")
        request.state.principal = principal
        return principal

    return dep
