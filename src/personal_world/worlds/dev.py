"""DEV-ONLY Worlds server. Never production, never exposed, loopback only.

Run it with::

    python -m personal_world.worlds.dev [--host 127.0.0.1] [--port 8765]

What makes this a development tool and not a product:

* it starts the in-process **reference provider** and seeds a config directory
  that points at it, so there is something real to look at on first load;
* it uses a **fake principal** - every ``/api`` route resolves to ``dev-owner``
  with no authentication of any kind;
* it uses the **test-only sender** from
  :mod:`personal_world.worlds.reference_provider`, not the production outbound
  path, which is still the refusing stub in
  :mod:`personal_world.worlds.confinement`;
* the demo secret is a literal in this file.

The one guardrail that is real: :func:`assert_loopback` refuses to start on
anything but ``127.0.0.1`` or ``::1``. The comparison is exact - no DNS, no
name resolution, no "localhost", no empty host - because a check that resolves a
name can be pointed somewhere else than it claims. It runs at start-up only:
the bind host is decided once, and uvicorn is not reconfigured afterwards.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from fastapi import FastAPI

from .authn import Principal
from .connect_routes import register_connect_routes
from .db import Database
from .memory_routes import register_memory_routes
from .memory_store import MemoryStore
from .reference_provider import ReferenceServer, reference_send
from .seed import SECRET_REF, seed_reference_config
from .server import build_app

__all__ = ["assert_loopback", "build_dev_app", "main", "DEV_TOKEN", "DEV_PRINCIPAL"]

#: Demo secret for the reference provider. It is a literal on purpose: this
#: server has no secret store and no authentication, so a real secret here
#: would be theatre.
DEV_TOKEN = "dev-ref-token"  # nosec B105  # a published demo value for the loopback-only, unauthenticated dev server; a real secret here would be theatre

#: The principal every ``/api`` route sees on this server.
DEV_PRINCIPAL = "dev-owner"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

#: Exactly these two. "localhost" is not here on purpose: it is a name, and a
#: name can be resolved to something that is not loopback.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})


def assert_loopback(host: str) -> None:
    """Refuse to start unless ``host`` is a loopback literal. Raises SystemExit.

    Exact string comparison, no DNS and no normalisation: ``0.0.0.0``,
    an address like ``192.0.2.1``, ``example.com``, ``localhost`` and ``""`` are all refused.
    """
    if not isinstance(host, str) or host not in LOOPBACK_HOSTS:
        allowed = ", ".join(sorted(LOOPBACK_HOSTS))
        raise SystemExit(
            f"refusing to bind {host!r}: the dev server only binds loopback ({allowed}). "
            "It has no authentication; never put it on a network."
        )


def dev_principal() -> str:
    """The fake identity every ``/api`` route resolves to on this server."""
    return DEV_PRINCIPAL


def _dev_owner() -> Principal:
    """The Memory and Connect routes want a :class:`Principal`, not its name.

    There is no session and no CSRF on this server, so the dev principal is handed back as the
    owner directly. It deliberately carries no step-up: a locked record stays locked even here.
    """
    return Principal("owner", DEV_PRINCIPAL, via="session")


def _config_dir(argument: str | None) -> Path:
    """``--config-dir``, then ``$PW_DEV_DIR``, then a fresh temporary directory."""
    chosen = argument or os.environ.get("PW_DEV_DIR")
    if chosen:
        return Path(chosen).expanduser()
    return Path(tempfile.mkdtemp(prefix="pw-worlds-dev-"))


def build_dev_app(config_dir: str | os.PathLike[str], reference: ReferenceServer) -> tuple[FastAPI, list[str]]:
    """Build the dev app, seed the reference config, then add Memory and Connect.

    This is the whole dev assembly without uvicorn, so tests can drive it in-process. It keeps every
    dev guarantee: loopback-only is enforced by :func:`main` before this is called (``assert_loopback``),
    the read API uses the fake principal, and outbound Connect tries go through
    :func:`~personal_world.worlds.reference_provider.reference_send` at *this* reference server, never
    the real network. The Memory store and its backups live under ``config_dir``; nothing is written
    outside it.

    Returns the app and the ids :func:`seed_reference_config` created.
    """
    config_dir = Path(config_dir)
    sender = reference_send({"REF_TOKEN": DEV_TOKEN}, allowed_ports={reference.port})
    app = build_app(
        config_dir,
        principal_dependency=dev_principal,
        send_override=sender,
        allowed_hosts=["127.0.0.1", "::1", "localhost"],
        secret_values=(DEV_TOKEN,),
    )
    created = seed_reference_config(app.state.store, reference.base_url)

    # Memory and Connect are registered the way production.py does, but with the dev principal as both
    # the owner and the agent caller. Everything lives under the temp config dir, so nothing is
    # persisted outside it and no real credentials are involved.
    data_dir = config_dir / "data"
    memory = MemoryStore(Database.in_dir(data_dir))
    app.state.memory = memory
    register_memory_routes(app, memory, data_dir / "backups", anyone=_dev_owner, owner=_dev_owner, clock=time.time)
    register_connect_routes(
        app,
        app.state.store,
        app.state.cards,
        owner=_dev_owner,
        send=sender,
        clock=time.time,
        audit=lambda event, detail, actor: memory.record_event(event, detail, actor=actor),
        secret_values=lambda: [DEV_TOKEN],
    )
    return app, created


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m personal_world.worlds.dev",
        description="DEV-ONLY Worlds server on loopback, with a seeded reference provider.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"loopback only (default {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"(default {DEFAULT_PORT})")
    parser.add_argument(
        "--config-dir",
        default=None,
        help="where to write the seeded config (default $PW_DEV_DIR, else a temp directory)",
    )
    return parser


def _banner(app: Any, host: str, port: int, config_dir: Path, reference: ReferenceServer) -> str:
    return "\n".join(
        [
            "",
            "  Personal World - Worlds (DEV-ONLY)",
            "  ----------------------------------",
            f"  api         http://{host}:{port}/api/boards/home",
            f"  health      http://{host}:{port}/healthz",
            f"  memory      http://{host}:{port}/api/memory/kept  (owner-only; no auth)",
            f"  connect     http://{host}:{port}/api/connect/try  (owner-only; no auth)",
            f"  config dir  {config_dir}",
            f"  reference   {reference.base_url}  (demo secret: {SECRET_REF} = {DEV_TOKEN})",
            f"  principal   {DEV_PRINCIPAL} for every route - there is no authentication",
            "",
            "  This server is for looking at Worlds locally. Do not expose it.",
            "",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    assert_loopback(args.host)  # before anything is built or bound

    import uvicorn  # imported here so --help and assert_loopback stay import-cheap

    reference = ReferenceServer(token=DEV_TOKEN).start()
    config_dir = _config_dir(args.config_dir)
    try:
        app, created = build_dev_app(config_dir, reference)
        print(_banner(app, args.host, args.port, config_dir, reference), file=sys.stderr)
        if created:
            print(f"  seeded {len(created)} config objects (already-present ones were left alone)\n", file=sys.stderr)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        reference.stop()
    return 0


if __name__ == "__main__":  # pragma: no cover - the entry point
    raise SystemExit(main())
