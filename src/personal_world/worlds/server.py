"""Worlds API: the read front door and the config CRUD surface.

Contract: docs/rebuild/CONTRACTS.md (C1 config files, C2 result envelope, C5 props).

This module is a **fresh** FastAPI app -- it does not import
:mod:`personal_world.app` and it adds no middleware, no sessions and no static
files. Everything it needs is passed in:

* ``config_dir`` -- the C1 config root (the store writes ``<root>/worlds/...``);
* ``principal_dependency`` -- a FastAPI dependency callable that every ``/api``
  route uses through ``Depends``. It raises 401 itself when the caller is not
  known; this module never invents an identity and never accepts an anonymous
  read;
* ``send`` -- the confinement seam. Only the runner reaches it.

What the routes may do, and nothing more:

* **Reading config** is a file read. **Saving config never sends a request** -
  no connect test, no run, no preview. That is a contract rule (C3), not an
  optimisation: saving must be safe to do from an editor while a provider is
  down;
* the only route that performs a fetch is ``GET /api/cards/{id}``, through
  :class:`~personal_world.worlds.cards.CardService`, and the runner refuses a
  write effect before the seam is ever reached;
* ``/healthz`` is public and says nothing but "this process is up" plus the
  commit it was built from;
* ``/api/needs-you`` is an empty list and ``/api/pickup`` does not exist yet.
  Both are honest about the surface that exists rather than half-built.

Errors are answers, not tracebacks: a refused config is a one-line ``detail``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError

from .cards import CardService, home_board_defs
from .config_store import MODEL_BY_KIND, ConfigInvalid, ConfigStore, EtagMismatch
from .config_store import _describe as _config_error  # one wording for every refusal
from .confinement import confined_request
from .runner import Runner

__all__ = ["build_app"]


# --------------------------------------------------------------- etags


def _format_etag(etag: str | None) -> str:
    """``abc123`` -> ``"abc123"`` (a quoted strong entity tag)."""
    if not etag:
        return ""
    if etag.startswith(("W/", '"')):
        return etag
    return f'"{etag}"'


def _parse_etag(header: str | None) -> str | None:
    """The hex digest a client sent, or None when the header is absent.

    Quotes and the weak prefix are stripped, so ``If-Match`` works whether the
    client echoed our quoted tag or wrote the bare digest.
    """
    if header is None:
        return None
    value = header.strip()
    if value.startswith("W/"):
        value = value[2:].strip()
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return value


def _check_kind(kind: str) -> None:
    if kind not in MODEL_BY_KIND:
        raise HTTPException(status_code=404, detail=f"no config kind {kind!r}")


# --------------------------------------------------------------- host guard


def parse_host(value: str | None) -> str | None:
    """The hostname in a Host header (port and IPv6 brackets handled), or None when malformed."""
    if not value or any(c in value for c in "@/\\ \t\r\n?#"):
        return None
    try:
        parts = urlsplit("//" + value)
        hostname = parts.hostname
        _ = parts.port  # raises ValueError on a bad port
    except ValueError:
        return None
    return hostname.lower() if hostname else None


class HostGuard:
    """Reject any request whose Host header is not an allowed name (stops DNS rebinding)."""

    def __init__(self, app: Any, allowed_hosts: list[str]):
        self.app = app
        self.allowed = {h.strip("[]").lower() for h in allowed_hosts}

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket"):
            raw = next((v.decode("latin-1") for k, v in scope["headers"] if k == b"host"), None)
            if parse_host(raw) not in self.allowed:
                if scope["type"] == "http":
                    await PlainTextResponse("invalid host", status_code=400)(scope, receive, send)
                return
        await self.app(scope, receive, send)


# --------------------------------------------------------------- app


def build_app(
    config_dir: str | os.PathLike[str],
    *,
    principal_dependency: Callable[..., Any],
    send_override: Callable[..., Any] | None = None,
    allowed_hosts: Iterable[str] | None = None,
    data_dir: str | os.PathLike[str] | None = None,
    secret_values: Iterable[str] = (),
    needs_you: Callable[[], list[Any]] | None = None,
    home_extra: Callable[[], list[dict[str, Any]]] | None = None,
    card_fallback: Callable[[str], dict[str, Any] | None] | None = None,
) -> FastAPI:
    """Build the Worlds app. Nothing here reads a secret but its redactor."""
    store = ConfigStore(config_dir)
    # Production sends ONLY through the confinement module. ``send_override`` exists for tests and
    # the loopback dev server; no production entrypoint passes it.
    runner = Runner(
        store,
        send_override if send_override is not None else confined_request,
        cache_dir=(Path(data_dir) / "cache") if data_dir is not None else None,
        secret_values=secret_values,
    )
    cards = CardService(store, runner)

    app = FastAPI(title="Personal World - Worlds", version="0.1.0")
    app.state.store = store
    app.state.runner = runner
    app.state.cards = cards
    if allowed_hosts is not None:
        app.add_middleware(HostGuard, allowed_hosts=list(allowed_hosts))

    principal = Depends(principal_dependency)

    # ------------------------------------------------------------ health

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        """Public. A liveness answer; it never touches config or the network."""
        return {"ok": True, "commit": os.environ.get("PW_COMMIT", "unknown")}

    # -------------------------------------------------------------- read

    @app.get("/api/boards/home", dependencies=[principal])
    def home_board() -> dict[str, Any]:
        """Display definitions for the home board: titles, sizes, field labels.

        No request id, path, provider name or fetched value crosses this route.
        """
        board = home_board_defs(store)
        extra = home_extra() if home_extra is not None else []
        out = {"id": "home", "title": "Home", "items": extra} if board is None else {**board, "items": [*board["items"], *extra]}
        # Nothing to show yet: Home is a guided start (connect a first service, then Memory), not an error.
        out["first_run"] = not out["items"]
        return out

    @app.get("/api/cards/{card_id}", dependencies=[principal])
    def card_envelope(card_id: str) -> dict[str, Any]:
        """The C2 envelope for one card. The only route that may reach the seam."""
        envelope = cards.build(card_id)
        if envelope is None and card_fallback is not None:
            envelope = card_fallback(card_id)
        if envelope is None:
            raise HTTPException(status_code=404, detail=f"no card {card_id!r}")
        return envelope

    @app.get("/api/needs-you", dependencies=[principal])
    def needs_you_route() -> list[Any]:
        """What waits on the owner (C6). Empty unless a provider of items is wired (production wires approvals)."""
        return needs_you() if needs_you is not None else []

    # ------------------------------------------------------------ config

    @app.get("/api/config/{kind}", dependencies=[principal])
    def list_config(kind: str) -> dict[str, Any]:
        """Every object of one kind with its etag, plus the files that would not load."""
        _check_kind(kind)
        items = []
        for kind_id, obj in sorted(store.snapshot().get(kind, {}).items()):
            items.append(
                {
                    "id": kind_id,
                    "etag": store.etag(kind, kind_id),
                    "object": obj.model_dump(mode="json"),
                }
            )
        return {"items": items, "errors": store.errors()}

    def lookup(kind: str, obj_id: str) -> Any:
        """The object, or a 404. An id the store will not even accept is a miss."""
        try:
            obj = store.get(kind, obj_id)
        except ConfigInvalid:
            raise HTTPException(status_code=404, detail=f"no {kind} {obj_id!r}") from None
        if obj is None:
            raise HTTPException(status_code=404, detail=f"no {kind} {obj_id!r}")
        return obj

    @app.get("/api/config/{kind}/{obj_id}", dependencies=[principal])
    def get_config(kind: str, obj_id: str) -> JSONResponse:
        """One object, with the etag a write must quote back in ``If-Match``."""
        _check_kind(kind)
        obj = lookup(kind, obj_id)
        return JSONResponse(
            content=obj.model_dump(mode="json"),
            headers={"etag": _format_etag(store.etag(kind, obj_id))},
        )

    @app.put("/api/config/{kind}/{obj_id}", dependencies=[principal])
    def put_config(kind: str, obj_id: str, request: Request, payload: Any = Body(default=None)) -> JSONResponse:
        """Validate, atomically write, and return the object with its new etag.

        Optimistic concurrency is mandatory: ``If-Match: <etag>`` updates,
        ``If-None-Match: *`` creates, and a request with neither is refused with
        428 rather than being allowed to guess. **No request is ever sent here** -
        saving config is not connecting to a provider.
        """
        _check_kind(kind)
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="body must be a JSON object")
        body_id = payload.get("id")
        if body_id != obj_id:
            raise HTTPException(
                status_code=422,
                detail=f"id in body ({body_id!r}) does not match id in url ({obj_id!r})",
            )
        try:
            obj = MODEL_BY_KIND[kind].model_validate(payload)
        except ValidationError as exc:
            # A refused config is a one-line answer. It never becomes a traceback.
            raise HTTPException(status_code=422, detail=_config_error(exc, f"invalid {kind}")) from None

        etag = _precondition(request, store, kind, obj_id)
        try:
            new_etag = store.save(kind, obj, etag=etag)
        except EtagMismatch as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except ConfigInvalid as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return JSONResponse(
            content=obj.model_dump(mode="json"),
            headers={"etag": _format_etag(new_etag)},
        )

    @app.delete("/api/config/{kind}/{obj_id}", dependencies=[principal], status_code=204)
    def delete_config(kind: str, obj_id: str, request: Request) -> Response:
        """Remove one object. 409 while anything refers to it or on a stale etag.

        ``If-Match: <etag>`` is optional for a valid object. A file that is invalid on disk (listed
        in ``errors``) can only be removed with the etag from that list.
        """
        _check_kind(kind)
        etag = _parse_etag(request.headers.get("if-match"))
        if etag == "*":
            raise HTTPException(status_code=428, detail="If-Match needs the current etag")
        try:
            store.delete(kind, obj_id, etag=etag)
        except EtagMismatch as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except ConfigInvalid as exc:
            missing = str(exc).startswith("no ") or "does not match" in str(exc)
            raise HTTPException(status_code=404 if missing else 409, detail=str(exc)) from None
        return Response(status_code=204)

    return app


# --------------------------------------------------------------- helpers


def _precondition(request: Request, store: ConfigStore, kind: str, obj_id: str) -> str | None:
    """The etag to save against, from ``If-Match`` or ``If-None-Match``.

    ``""`` means "must not exist yet" (the store's create-only form).
    """
    if_match = request.headers.get("if-match")
    if if_match is not None:
        value = _parse_etag(if_match)
        if value == "*":
            raise HTTPException(status_code=428, detail="If-Match needs the current etag; use If-None-Match: * to create")
        if not value:
            raise HTTPException(status_code=400, detail="If-Match must carry an etag")
        return value
    if_none_match = request.headers.get("if-none-match")
    if if_none_match is not None:
        if if_none_match.strip() != "*":
            raise HTTPException(
                status_code=428,
                detail="If-None-Match must be * to create, or send If-Match to update",
            )
        return ""
    raise HTTPException(
        status_code=428,
        detail="If-Match: <etag> to update, If-None-Match: * to create",
    )
