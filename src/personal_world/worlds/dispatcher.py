"""C3 action authority: authorizations, durable single dispatch, receipts.

Lifecycle (docs/rebuild/CONTRACTS.md C3). An action runs only through here:

    request_authorization -> (approve | project-home approval | policy "never") -> execute

``execute`` consumes the authorization and writes the execution INTENT in ONE
``BEGIN IMMEDIATE`` transaction whose UPDATE only matches an *approved, unexpired* authorization
whose action_version still equals the current one. Then the row moves to DISPATCHING (committed),
exactly ONE network attempt is made OUTSIDE any transaction (no retries), and the outcome is
recorded: SUCCEEDED, FAILED (only with evidence the action did not run) or UNKNOWN. A crash at any
point leaves INTENT/DISPATCHING, which :meth:`Dispatcher.recover` turns into UNKNOWN at startup;
nothing is ever re-sent. A retry is a NEW authorization that carries a warning.

Authority: an owner session with fresh step-up approves operations Worlds governs itself; an
operation Project Home governs is approved there and recorded here (``project_home:<id>``); a
token (agent) never approves. ``approval: never`` is an owner-written config choice.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import sqlite3
import time
import uuid
from typing import Any, Callable, Iterable, Literal

from .authn import Principal
from .config_store import ConfigStore
from .confinement import ConfinementError, RawResponse, confined_request
from .db import Database, register_migrations
from .models import Action, Provider, Request, canonical_json, send_scoped
from .runner import redact

log = logging.getLogger(__name__)
DEFAULT_TTL_S = 600
MAX_PARAMS_BYTES = 8192
# 4xx replies that prove the server did NOT run the action. 408/409/425/429 are ambiguous: UNKNOWN.
_NOT_EXECUTED_4XX = {400, 401, 402, 403, 404, 405, 406, 410, 411, 413, 414, 415, 421, 422, 426, 428, 431}

register_migrations("dispatcher", [
    (1, """CREATE TABLE authorizations (
        id TEXT PRIMARY KEY, action_id TEXT NOT NULL, action_version TEXT NOT NULL, caller TEXT NOT NULL,
        destination TEXT NOT NULL, params_hash TEXT NOT NULL, params_json TEXT NOT NULL,
        created_at REAL NOT NULL, expires_at REAL NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('pending','approved','denied','expired','invalidated','consumed')),
        authority TEXT, approved_at REAL, approved_by TEXT, step_up_at REAL,
        idempotency_key TEXT, retry_of TEXT, previous_may_have_run INTEGER NOT NULL DEFAULT 0);
CREATE TABLE executions (
        id TEXT PRIMARY KEY, authorization_id TEXT NOT NULL UNIQUE REFERENCES authorizations(id),
        intent_at REAL NOT NULL, dispatch_started_at REAL, finished_at REAL,
        state TEXT NOT NULL CHECK (state IN ('INTENT','DISPATCHING','SUCCEEDED','FAILED','UNKNOWN')),
        status_code INTEGER, evidence_redacted TEXT, idempotency_key TEXT);
CREATE INDEX idx_auth_state ON authorizations(state, expires_at)"""),
    (2, """ALTER TABLE executions ADD COLUMN owner_id TEXT;
CREATE TABLE leases (instance_id TEXT PRIMARY KEY, heartbeat REAL NOT NULL)"""),
    (3, """ALTER TABLE leases ADD COLUMN pid INTEGER;
ALTER TABLE leases ADD COLUMN boot_id TEXT;
ALTER TABLE leases ADD COLUMN started TEXT"""),
    (4, "ALTER TABLE leases ADD COLUMN host TEXT"),
])

LEASE_TTL_S = 30.0
LEASE_RENEW_S = LEASE_TTL_S / 3   # how often a live process renews; a lease older than this has missed a beat


def process_identity() -> tuple[str, int, str, str]:
    """(boot id, pid, process start time, host name). The host name is the container id in Docker, so two
    containers sharing a volume (both pid 1, same kernel boot id) are told apart."""
    try:
        boot = open("/proc/sys/kernel/random/boot_id").read().strip()
    except OSError:
        boot = "unknown"
    try:
        started = open("/proc/self/stat").read().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        started = "0"
    return boot, os.getpid(), started, socket.gethostname()


class DispatchError(Exception):
    """Base class: the caller asked for something the authority rules refuse."""


class NotPermitted(DispatchError):
    pass


class NotConsumable(DispatchError):
    """The authorization cannot be consumed (not approved, expired, invalidated, already used...)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class BadRequest(DispatchError):
    pass


Send = Callable[..., "RawResponse | ConfinementError"]
PHVerifier = Callable[[str, dict], bool]


def params_hash(params: dict) -> str:
    return hashlib.sha256(canonical_json(params).encode()).hexdigest()


def destination_of(provider: Provider) -> str:
    return f"{provider.id}:{hashlib.sha256((provider.base_url + provider.path_prefix).encode()).hexdigest()[:16]}"


def classify_outcome(result: Any) -> tuple[Literal["SUCCEEDED", "FAILED", "UNKNOWN"], int | None, str | None]:
    """(state, status_code, error_class). FAILED only with evidence the action did not run."""
    if isinstance(result, RawResponse):
        code = result.status_code
        if 200 <= code < 300:
            return "SUCCEEDED", code, None
        if code in _NOT_EXECUTED_4XX:
            return "FAILED", code, "http_4xx"
        return "UNKNOWN", code, "http_5xx" if code >= 500 else "http_4xx" if code >= 400 else "redirect_refused"
    if isinstance(result, ConfinementError):
        if result.pre_send or result.error_class in ("confinement_denied", "auth_failed"):
            return "FAILED", result.status_code, result.error_class  # nothing was sent: it provably did not run
        return "UNKNOWN", result.status_code, result.error_class
    return "UNKNOWN", None, "malformed"


def _room_receipt(result: RawResponse) -> tuple[str, str | None, str | None]:
    """A room answers 2xx with a receipt {ok, summary, changed, at} (ROOM rule 9). ``ok: false`` is the
    room's own refusal/failure: FAILED when it says nothing changed, UNKNOWN when it says something did
    (or says nothing), and an unreadable receipt is UNKNOWN: never a silent success."""
    try:
        doc = json.loads(result.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return "UNKNOWN", "malformed", None
    if not isinstance(doc, dict) or not isinstance(doc.get("ok"), bool):
        return "UNKNOWN", "malformed", None
    summary = doc.get("summary") if isinstance(doc.get("summary"), str) else None
    if doc["ok"]:
        return "SUCCEEDED", None, summary
    changed = doc.get("changed")
    return ("FAILED" if changed in (None, [], {}, "", False) and "changed" in doc else "UNKNOWN"), "http_4xx", summary


class Dispatcher:
    def __init__(
        self,
        db: Database,
        store: ConfigStore,
        *,
        send: Send | None = None,
        clock: Callable[[], float] = time.time,
        secret_values: Iterable[str] = (),
        governed_by_project_home: Callable[[Provider], bool] | None = None,
        project_home_verifier: PHVerifier | None = None,
        ttl_s: int = DEFAULT_TTL_S,
        identity: tuple[str, int, str, str] | None = None,
    ):
        self._db, self._store = db, store
        self._send = send if send is not None else confined_request
        self._clock, self._secret_source = clock, secret_values   # iterated at redaction time (may be live)
        # Fail closed: by default a provider marked (or, for room0, defaulting to) Project Home governance
        # can only be approved there.
        self._ph_governs = governed_by_project_home or (lambda provider: provider.governed_by_project_home())
        self._ph_verify = project_home_verifier
        self._ttl = ttl_s
        self.identity = identity or process_identity()
        self.instance_id = uuid.uuid4().hex   # this process's identity; its rows are protected by a live lease
        self.heartbeat()
        self._unsubscribe = store.on_change(self._on_actions_changed)

    # ------------------------------------------------------------ lease

    def heartbeat(self) -> None:
        """Renew this process's lease. Call it regularly (production runs a timer); it is also
        renewed on every execute, so a busy process is never mistaken for a dead one."""
        with self._db.write_tx() as tx:
            tx.execute("INSERT INTO leases(instance_id, heartbeat, pid, boot_id, started, host) VALUES (?,?,?,?,?,?) "
                       "ON CONFLICT(instance_id) DO UPDATE SET heartbeat=excluded.heartbeat",
                       (self.instance_id, self._clock(), self.identity[1], self.identity[0], self.identity[2], self.identity[3]))

    # ------------------------------------------------------------ helpers

    def _resolve(self, action_id: str) -> tuple[Action, Request, Provider]:
        action = self._store.get("action", action_id)
        request = self._store.get("request", action.request) if action else None
        provider = self._store.get("provider", request.provider) if request else None
        if not (action and request and provider):
            raise BadRequest(f"action {action_id!r} is not configured")
        return action, request, provider

    def _row(self, c: sqlite3.Connection, authorization_id: str) -> sqlite3.Row:
        row = c.execute("SELECT * FROM authorizations WHERE id=?", (authorization_id,)).fetchone()
        if row is None:
            raise BadRequest("no such authorization")
        return row

    @staticmethod
    def _owner_ok(principal: Principal) -> None:
        if not principal.is_owner or principal.via != "session":
            raise NotPermitted("only the owner can do that")

    # -------------------------------------------------------- authorization

    def can_see(self, principal: Principal, action: Action) -> bool:
        """Agents see only adopted, exposed actions inside their scope; the owner sees all."""
        return principal.is_owner or (action.state == "adopted" and action.exposed and principal.allows_scope(action.scope))

    def list_actions(self, principal: Principal) -> list[Action]:
        return [obj for kind, obj in self._store.iter_all() if kind == "action" and self.can_see(principal, obj)]

    def request_authorization(self, principal: Principal, action_id: str, params: dict | None = None,
                              idempotency_key: str | None = None, *, _retry_of: str | None = None,
                              _warn: bool = False) -> dict:
        action, request, provider = self._resolve(action_id)
        if not self.can_see(principal, action):
            raise NotPermitted("that action is not available to this caller")
        if action.state != "adopted":  # a proposed (or refused/expired) action is inert for everyone, the owner included
            raise NotPermitted(f"that action is {action.state}, not adopted")
        params = {} if params is None else params
        if not isinstance(params, dict) or len(canonical_json(params).encode()) > MAX_PARAMS_BYTES:
            raise BadRequest("params must be a JSON object under 8 KiB")
        if params and (request.body is not None or request.method in ("GET", "HEAD")):
            raise BadRequest("this action does not take params")
        if action.idempotency == "required" and not idempotency_key:
            raise BadRequest("this action requires an idempotency key")
        if idempotency_key is not None and not (1 <= len(idempotency_key) <= 200 and idempotency_key.isprintable()
                                                and "\r" not in idempotency_key and "\n" not in idempotency_key):
            raise BadRequest("bad idempotency key")
        version = self._store.action_version(action_id)
        now = self._clock()
        governed = self._ph_governs(provider)
        # "never" skips approval only when the owner wrote it. For a WRITE effect it also needs the
        # owner's explicit waiver and access: write, and only an owner caller benefits: an agent's
        # write always waits for the owner. A read-labelled action that would write is never waived.
        write_effect = request.resolved_effect() == "write"
        waived_write = action.owner_waives_approval and action.access == "write" and principal.is_owner
        auto = (action.approval == "never" and _retry_of is None and not governed
                and (not write_effect or waived_write) and not (write_effect and action.access != "write"))
        aid = uuid.uuid4().hex
        with self._db.write_tx() as tx:
            tx.execute(
                "INSERT INTO authorizations(id,action_id,action_version,caller,destination,params_hash,params_json,created_at,"
                "expires_at,state,authority,approved_at,approved_by,idempotency_key,retry_of,previous_may_have_run) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (aid, action_id, version, principal.id, destination_of(provider), params_hash(params),
                 canonical_json(params), now, now + self._ttl, "approved" if auto else "pending",
                 "policy:never" if auto else None, now if auto else None, "policy:never" if auto else None, idempotency_key, _retry_of, int(_warn)))
        return self.get_authorization(aid)

    def get_authorization(self, authorization_id: str) -> dict:
        out = dict(self._row(self._db.conn(), authorization_id))
        out["previous_may_have_run"] = bool(out["previous_may_have_run"])
        return out

    def approve(self, principal: Principal, authorization_id: str) -> dict:
        """The owner confirms, with fresh step-up. Never available for Project Home-governed operations."""
        self._owner_ok(principal)
        if not principal.has_step_up(self._clock()):
            raise NotPermitted("confirm it's you first (step-up required)")
        now = self._clock()
        with self._db.write_tx() as tx:
            row = self._row(tx, authorization_id)
            _, _, provider = self._resolve(row["action_id"])
            if self._ph_governs(provider):
                raise NotPermitted("this operation is approved in Project Home")
            self._check_approvable(row, now)
            tx.execute("UPDATE authorizations SET state='approved', authority='worlds_owner', approved_at=?, approved_by=?, "
                       "step_up_at=? WHERE id=? AND state='pending'", (now, principal.id, principal.step_up_at, authorization_id))
        return self.get_authorization(authorization_id)

    def record_project_home_approval(self, authorization_id: str, ph_approval_id: str) -> dict:
        """Record an approval made in Project Home (verified there), for operations it governs."""
        if self._ph_verify is None:
            raise NotPermitted("Project Home approval is not available")
        now = self._clock()
        with self._db.write_tx() as tx:
            row = self._row(tx, authorization_id)
            _, _, provider = self._resolve(row["action_id"])
            if not self._ph_governs(provider):
                raise NotPermitted("Project Home does not govern this operation")
            self._check_approvable(row, now)
            if not self._ph_verify(ph_approval_id, dict(row)):
                raise NotPermitted("Project Home did not confirm that approval")
            tx.execute("UPDATE authorizations SET state='approved', authority=?, approved_at=?, approved_by=? "
                       "WHERE id=? AND state='pending'", (f"project_home:{ph_approval_id}", now, "project_home", authorization_id))
        return self.get_authorization(authorization_id)

    def _check_approvable(self, row: sqlite3.Row, now: float) -> None:
        if row["state"] != "pending":
            raise NotConsumable(f"authorization is {row['state']}")
        if now >= row["expires_at"]:
            raise NotConsumable("authorization expired")
        if self._store.action_version(row["action_id"]) != row["action_version"]:
            raise NotConsumable("the action changed since it was requested")

    def deny(self, principal: Principal, authorization_id: str) -> dict:
        """Owner denies, or the requesting caller cancels, BEFORE anything was consumed."""
        with self._db.write_tx() as tx:
            row = self._row(tx, authorization_id)
            if not (principal.is_owner or principal.id == row["caller"]):
                raise NotPermitted("not your authorization")
            cur = tx.execute("UPDATE authorizations SET state='denied' WHERE id=? AND state IN ('pending','approved')",
                             (authorization_id,))
            if cur.rowcount != 1:
                raise NotConsumable(f"authorization is {row['state']}")
        return self.get_authorization(authorization_id)

    def _on_actions_changed(self, action_ids: list[str]) -> None:
        """Config changed an action/request/provider: pending authorizations for it no longer match."""
        if not action_ids:
            return
        with self._db.write_tx() as tx:
            for action_id in action_ids:
                version = self._store.action_version(action_id)
                tx.execute("UPDATE authorizations SET state='invalidated' WHERE action_id=? AND state IN ('pending','approved') "
                           "AND (? IS NULL OR action_version != ?)", (action_id, version, version))

    def expire_due(self) -> int:
        with self._db.write_tx() as tx:
            cur = tx.execute("UPDATE authorizations SET state='expired' WHERE state IN ('pending','approved') AND expires_at<=?",
                             (self._clock(),))
        return cur.rowcount

    # ------------------------------------------------------------ execution

    def _consume(self, principal: Principal, authorization_id: str) -> tuple[sqlite3.Row, str, Action, Request, Provider]:
        """One transaction: approved+unexpired+current-version authorization -> consumed, execution INTENT."""
        now = self._clock()
        with self._db.write_tx() as tx:
            row = self._row(tx, authorization_id)
            if not (principal.is_owner or principal.id == row["caller"]):
                raise NotPermitted("not your authorization")
            try:
                action, request, provider = self._resolve(row["action_id"])
            except BadRequest:
                raise NotConsumable("the action is no longer configured") from None
            if action.state != "adopted":
                raise NotConsumable(f"the action is {action.state}, not adopted")
            current = self._store.action_version(row["action_id"])
            if row["params_hash"] != params_hash(json.loads(row["params_json"])):
                raise NotConsumable("stored parameters do not match their hash")
            cur = tx.execute(
                "UPDATE authorizations SET state='consumed' WHERE id=? AND state='approved' AND expires_at>? AND action_version=?",
                (authorization_id, now, current))
            if cur.rowcount != 1:
                state = row["state"]
                if state == "approved" and now >= row["expires_at"]:
                    state = "expired"
                elif state == "approved":
                    state = "invalidated"
                raise NotConsumable(f"authorization is {state}")
            execution_id = uuid.uuid4().hex
            tx.execute("INSERT INTO executions(id,authorization_id,intent_at,state,idempotency_key,owner_id) VALUES (?,?,?,'INTENT',?,?)",
                       (execution_id, authorization_id, now, row["idempotency_key"], self.instance_id))
        return row, execution_id, action, request, provider

    def execute(self, principal: Principal, authorization_id: str) -> dict:
        row, execution_id, action, request, provider = self._consume(principal, authorization_id)
        self.heartbeat()
        with self._db.write_tx() as tx:
            moved = tx.execute("UPDATE executions SET state='DISPATCHING', dispatch_started_at=? WHERE id=? AND state='INTENT'",
                               (self._clock(), execution_id))
        if moved.rowcount != 1:
            # Recovery settled the row (UNKNOWN) between consume and dispatch: do NOT send.
            raise DispatchError("this execution was settled before it was sent; request a new authorization")
        sent = request
        updates: dict[str, Any] = {}
        params = json.loads(row["params_json"])
        if params:
            updates["body"] = params
        if row["idempotency_key"]:
            updates["headers"] = {**request.headers, "Idempotency-Key": row["idempotency_key"]}
        if updates:
            sent = request.model_copy(update=updates)
        effect = request.resolved_effect()
        if self._db.conn().in_transaction:  # never hold a transaction across the network
            raise RuntimeError("transaction open across dispatch")
        try:
            result = send_scoped(self._send, provider, sent, effect=effect)  # exactly one attempt
        except Exception as exc:  # BaseException (a crash) deliberately propagates: row stays DISPATCHING
            result = ConfinementError("connection", f"sender error: {type(exc).__name__}")
        state, status, error_class = classify_outcome(result)
        room_summary = None
        if state == "SUCCEEDED" and provider.kind == "room0" and isinstance(result, RawResponse):
            state, error_class, room_summary = _room_receipt(result)
        note = redact(getattr(result, "note", "") or "", tuple(self._secret_source))[:300] if isinstance(result, ConfinementError) else ""
        evidence = {"method": request.method, "path": request.path, "status_code": status, "error_class": error_class,
                    "duration_ms": getattr(result, "duration_ms", None)}
        if note:
            evidence["note"] = note
        if room_summary:
            evidence["summary"] = redact(room_summary, tuple(self._secret_source))[:200]
        with self._db.write_tx() as tx:
            cur = tx.execute("UPDATE executions SET state=?, status_code=?, evidence_redacted=?, finished_at=? "
                             "WHERE id=? AND state='DISPATCHING'",
                             (state, status, json.dumps(evidence), self._clock(), execution_id))
        if cur.rowcount != 1:
            # Someone (recovery) already settled this row as UNKNOWN. UNKNOWN stays: do not overwrite it.
            log.warning("execution %s was settled elsewhere; keeping its recorded state", execution_id)
        return self.receipt(execution_id)

    def recover(self) -> int:
        """INTENT/DISPATCHING rows whose owning process is gone become UNKNOWN. Never re-sent.

        An owner is gone when its lease lapsed (LEASE_TTL_S), or when its lease shows a previous boot
        of this host, or the same pid with a different start time (this process is its restart): those
        are settled at once, so a fast restart does not wait out the lease. This process's own rows
        and any live process's rows are never touched.
        """
        now = self._clock()
        boot, pid, started, host = self.identity
        alive = {self.instance_id}
        for lease in self._db.conn().execute(
                "SELECT instance_id, heartbeat, pid, boot_id, started, host FROM leases").fetchall():
            if lease["instance_id"] == self.instance_id:
                continue
            expired = lease["heartbeat"] <= now - LEASE_TTL_S
            same_host = lease["host"] is not None and lease["host"] == host
            # Identity can only settle a lease EARLY when it is provably this host's own past: the host
            # rebooted, or this process is the restart of that pid (same boot, same pid, new start time)
            # and the old one has missed a heartbeat. Anything else (another container or machine sharing
            # the volume) is alive until its lease actually expires.
            rebooted = same_host and lease["boot_id"] is not None and lease["boot_id"] != boot
            restarted = (same_host and lease["boot_id"] == boot and lease["pid"] == pid and lease["started"] != started
                         and lease["heartbeat"] <= now - LEASE_RENEW_S)
            if not (expired or rebooted or restarted):
                alive.add(lease["instance_id"])
        evidence = json.dumps({"error_class": None, "note": "interrupted before a result was recorded"})
        marks = ",".join("?" for _ in alive)
        with self._db.write_tx() as tx:
            cur = tx.execute(
                f"UPDATE executions SET state='UNKNOWN', finished_at=?, evidence_redacted=? "
                f"WHERE state IN ('INTENT','DISPATCHING') AND (owner_id IS NULL OR owner_id NOT IN ({marks}))",  # nosec B608  # {marks} is only generated "?" placeholders, never data
                (now, evidence, *alive))
            tx.execute("DELETE FROM leases WHERE instance_id != ? AND instance_id NOT IN (%s) AND heartbeat <= ?" % marks,  # nosec B608  # %s is only generated "?" placeholders, never data
                       (self.instance_id, *alive, now - 10 * LEASE_TTL_S))
        return cur.rowcount

    def request_retry(self, principal: Principal, execution_id: str) -> dict:
        """A NEW authorization for the same action; always needs a fresh approval, and warns."""
        ex = self._db.conn().execute("SELECT e.*, a.action_id, a.caller, a.params_json FROM executions e "
                                     "JOIN authorizations a ON a.id=e.authorization_id WHERE e.id=?", (execution_id,)).fetchone()
        if ex is None:
            raise BadRequest("no such execution")
        if not (principal.is_owner or principal.id == ex["caller"]):
            raise NotPermitted("not your execution")
        if ex["state"] in ("INTENT", "DISPATCHING"):
            raise NotConsumable("that execution is still in progress")
        warn = ex["state"] in ("UNKNOWN", "SUCCEEDED")
        return self.request_authorization(principal, ex["action_id"], json.loads(ex["params_json"]) or None,
                                          ex["idempotency_key"], _retry_of=execution_id, _warn=warn)

    # -------------------------------------------------------------- receipts

    def receipt(self, execution_id: str) -> dict:
        row = self._db.conn().execute(
            "SELECT e.id AS execution_id, e.state, e.status_code, e.evidence_redacted, e.intent_at, e.dispatch_started_at, "
            "e.finished_at, e.idempotency_key, a.id AS authorization_id, a.caller, a.action_id, a.action_version, a.authority, "
            "a.approved_at, a.approved_by, a.destination, a.retry_of, a.previous_may_have_run "
            "FROM executions e JOIN authorizations a ON a.id=e.authorization_id WHERE e.id=?", (execution_id,)).fetchone()
        if row is None:
            raise BadRequest("no such execution")
        out = dict(row)
        out["evidence"] = json.loads(out.pop("evidence_redacted") or "{}")
        out["previous_may_have_run"] = bool(out["previous_may_have_run"])
        return out

    def list_receipts(self, limit: int = 50) -> list[dict]:
        ids = [r["id"] for r in self._db.conn().execute("SELECT id FROM executions ORDER BY intent_at DESC LIMIT ?", (limit,))]
        return [self.receipt(i) for i in ids]

    def close(self) -> None:
        self._unsubscribe()
