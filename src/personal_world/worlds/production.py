"""Production assembly: Database + Auth + owner policy + ConfigStore + Runner + Dispatcher.

``create_app`` is the ONLY production entrypoint. It never accepts a sender override (every
outbound request goes through ``confinement.confined_request``), has no development bypass, and
fails closed: with no valid ``owner.yaml`` nobody can sign in and cookie-authenticated writes are
refused. Startup runs dispatcher recovery (INTENT/DISPATCHING become UNKNOWN; nothing is re-sent).
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI

from ..oidc import OIDCService
from ..push import PushHub
from .actions_routes import register_action_routes
from .auth_routes import parse_trusted_proxies, register_auth_routes
from .authn import Auth, load_csrf_key, load_key, principal_dependency
from .companion_routes import register_companion_routes
from .connect_routes import register_connect_routes
from .db import Database
from .dispatcher import LEASE_TTL_S, Dispatcher
from .memory_routes import register_memory_routes
from .memory_store import MemoryStore
from .owner import load_owner_policy, strong_secret
from .push_routes import register_push_routes
from .room0 import Room0Client, RoomService
from .room_routes import register_room_routes
from .secrets import resolve_secret_ref
from .server import build_app
from .static_routes import register_static_routes


class LiveSecrets:
    """Every credential the providers currently resolve to, looked up at redaction time, so a secret
    rotated after startup is still scrubbed from notes and receipts. Iterating yields values only."""

    def __init__(self, store: Any, extra: tuple[str, ...] = ()):
        self._store, self._extra = store, tuple(extra)

    def __iter__(self):
        yield from self._extra
        for kind, obj in self._store.iter_all():
            if kind == "provider" and obj.auth.secret_ref:
                value = resolve_secret_ref(obj.auth.secret_ref)
                if value:
                    yield value


def create_app(config_dir: str | os.PathLike[str], data_dir: str | os.PathLike[str], *, secret_values: tuple[str, ...] = (),
               maintenance_interval: float = LEASE_TTL_S / 3, trusted_proxies: tuple[Any, ...] | None = None) -> FastAPI:
    config_dir, data_dir = Path(config_dir), Path(data_dir)
    policy = load_owner_policy(config_dir)
    if policy.file and policy.file.bootstrap.enabled:
        value = resolve_secret_ref(policy.file.bootstrap.secret_ref)
        if value and not strong_secret(value):  # fail closed: never run with a guessable bootstrap secret
            raise SystemExit("the bootstrap secret is too weak: use at least 32 hex or 22 base64url characters, e.g. "
                             "python -c \"import secrets;print(secrets.token_urlsafe(32))\"")
    db = Database.in_dir(data_dir)
    origins = frozenset({policy.public_origin}) if policy.public_origin else frozenset()
    # Sessions are bound to the owner identity: editing owner.yaml's issuer/subject ends them all.
    auth = Auth(db, load_csrf_key(data_dir), origins, binding=lambda: load_owner_policy(config_dir).binding())
    owner_dep = principal_dependency(auth, owner_only=True)
    anyone_dep = principal_dependency(auth, owner_only=False)

    holder: dict[str, Dispatcher] = {}

    def needs_you() -> list[dict[str, Any]]:
        d = holder["d"]
        room_needs = holder["rooms"].needs()
        d.expire_due()
        now = auth.clock()
        rows = db.conn().execute(
            "SELECT id, action_id, created_at, caller FROM authorizations WHERE state='pending' AND expires_at>? ORDER BY created_at",
            (now,))
        return [{"id": f"authorization:{r['id']}", "text": f"Approve '{r['action_id']}' requested by {r['caller']}",
                 "source": "actions", "created_at": r["created_at"],
                 "action": {"kind": "approve", "authorization_id": r["id"]}} for r in rows] + room_needs

    hosts = [urlsplit(policy.public_origin).hostname] if policy.public_origin else []
    from .config_store import ConfigStore

    live = LiveSecrets(ConfigStore(config_dir), secret_values)        # a second read-only view for redaction
    app = build_app(config_dir, principal_dependency=owner_dep, allowed_hosts=hosts or ["invalid.invalid"],
                    data_dir=data_dir, secret_values=live, needs_you=needs_you,
                    home_extra=lambda: holder["rooms"].home_items(), card_fallback=lambda cid: holder["rooms"].card(cid))
    live._store = app.state.store
    holder["rooms"] = RoomService(app.state.store, Room0Client(app.state.store))
    app.state.rooms = holder["rooms"]
    dispatcher = Dispatcher(db, app.state.store, secret_values=live)
    holder["d"] = dispatcher
    # Recovery runs HERE, before create_app returns, so no route can be served first. Rows owned by a
    # live process (a lease renewed within LEASE_TTL_S) are left alone; the maintenance thread keeps
    # renewing this process's lease and retries recovery for rows whose owner has since died.
    recovered = dispatcher.recover()
    app.state.db, app.state.auth, app.state.dispatcher, app.state.recovered = db, auth, dispatcher, recovered
    stop = threading.Event()

    def maintain() -> None:
        while not stop.wait(maintenance_interval):
            try:
                dispatcher.heartbeat()
                dispatcher.recover()
                dispatcher.expire_due()
            except Exception:  # nosec B110  # never let housekeeping kill the process
                pass

    threading.Thread(target=maintain, name="worlds-maintenance", daemon=True).start()
    app.router.on_shutdown.append(stop.set)

    oidc = {"svc": None}

    def oidc_service() -> Any:
        return oidc["svc"]

    flow_key = load_key(data_dir, "oidc-flow.key")   # persisted: any worker can finish a login another started

    class _Lazy:
        def client(self):
            if oidc["svc"] is None:
                oidc["svc"] = OIDCService(config_dir, flow_key=flow_key)
            return oidc["svc"].client()

    proxies = trusted_proxies if trusted_proxies is not None else parse_trusted_proxies(os.environ.get("PW_TRUSTED_PROXIES"))
    register_auth_routes(app, auth, lambda: load_owner_policy(config_dir), _Lazy(), trusted_proxies=proxies)
    register_action_routes(app, auth, dispatcher, anyone=anyone_dep, owner=owner_dep)
    memory = MemoryStore(db)
    app.state.memory = memory
    register_memory_routes(app, memory, data_dir / "backups", anyone=anyone_dep, owner=owner_dep, clock=auth.clock)
    register_connect_routes(app, app.state.store, app.state.cards, owner=owner_dep, clock=auth.clock,
                            audit=lambda event, detail, actor: memory.record_event(event, detail, actor=actor),
                            secret_values=lambda: list(live))
    register_room_routes(app, holder["rooms"], owner=owner_dep)
    register_companion_routes(app, app.state.store, owner=owner_dep)   # owner session only; confined; whitelisted
    # The front door's push stores live under data/push/ and never touch the old identity layer.
    push_dir = data_dir / "push"
    hub = PushHub(data_dir, mode="single", store_path=lambda person, kind: push_dir / person / f"{kind}.json")
    register_push_routes(app, hub, owner=owner_dep, anyone=anyone_dep)
    # Must remain last: the SPA fallback must not capture API or health routes.
    register_static_routes(app, os.environ.get("PW_STATIC_DIR", Path(__file__).parents[1] / "static" / "app"))
    return app


def app_from_env() -> FastAPI:
    """``uvicorn personal_world.worlds.production:app_from_env --factory``. Both directories are required."""
    config, data = os.environ.get("PW_CONFIG_DIR"), os.environ.get("PW_DATA_DIR")
    if not config or not data:
        raise SystemExit("PW_CONFIG_DIR and PW_DATA_DIR must both be set")
    try:
        proxies = parse_trusted_proxies(os.environ.get("PW_TRUSTED_PROXIES"))
    except ValueError as exc:
        raise SystemExit(f"PW_TRUSTED_PROXIES is not a list of IPs/CIDRs: {exc}") from None
    return create_app(config, data, trusted_proxies=proxies)
