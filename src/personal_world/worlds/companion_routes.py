"""Owner-only HTTP routes that proxy to Companion (see :mod:`personal_world.worlds.companion`).

Every route needs the OWNER session: an agent token gets 403, and a mutating call from a cookie session also needs the
CSRF header and an allowed Origin (both enforced by :class:`Auth`). The browser never sees Companion's address or token.
When Companion cannot answer, the reply is a fixed honest body ("Companion isn't answering", state ``unknown``), never
a guess and never upstream text.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Body, Depends, FastAPI, Query
from fastapi.responses import JSONResponse

from .authn import Principal
from .companion import BadInput, Companion, NotConfigured, Unavailable
from .confinement import confined_request

__all__ = ["register_companion_routes"]

NOT_ANSWERING = "Companion isn't answering."


def register_companion_routes(app: FastAPI, store: Any, *, owner: Callable[..., Principal],
                              send: Callable[..., Any] = confined_request) -> Companion:
    client = Companion(store, send)

    def run(call: Callable[[], dict[str, Any]]) -> JSONResponse:
        try:
            return JSONResponse(call())
        except NotConfigured:
            return JSONResponse({"state": "not_configured", "text": "Companion isn't set up."}, status_code=503)
        except BadInput as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        except Unavailable as exc:
            # A fixed reason word and the fixed sentence: nothing from upstream is echoed.
            return JSONResponse({"state": "unknown", "text": NOT_ANSWERING, "reason": exc.reason}, status_code=502)

    @app.post("/api/companion/turn")
    def turn(payload: Any = Body(default=None), p: Principal = Depends(owner)) -> JSONResponse:
        return run(lambda: client.turn(payload))

    @app.get("/api/companion/threads")
    def threads(p: Principal = Depends(owner)) -> JSONResponse:
        return run(client.threads)

    @app.get("/api/companion/threads/{thread_id}")
    def thread(thread_id: str, after: int = Query(0, ge=0, le=1_000_000), p: Principal = Depends(owner)) -> JSONResponse:
        return run(lambda: client.thread(thread_id, after))

    @app.get("/api/companion/context")
    def context(q: str = Query("", max_length=500), p: Principal = Depends(owner)) -> JSONResponse:
        return run(lambda: client.context(q))

    @app.get("/api/companion/changes")
    def changes(since: str | None = Query(None, max_length=200), p: Principal = Depends(owner)) -> JSONResponse:
        return run(lambda: client.changes(since))

    @app.post("/api/companion/grants")
    def create_grant(payload: Any = Body(default=None), p: Principal = Depends(owner)) -> JSONResponse:
        return run(lambda: client.create_grant(payload))

    @app.get("/api/companion/grants/{grant_id}")
    def get_grant(grant_id: str, p: Principal = Depends(owner)) -> JSONResponse:
        return run(lambda: client.grant(grant_id))

    @app.delete("/api/companion/grants/{grant_id}")
    def revoke_grant(grant_id: str, p: Principal = Depends(owner)) -> JSONResponse:
        return run(lambda: client.revoke_grant(grant_id))

    @app.get("/api/companion/health")
    def health(p: Principal = Depends(owner)) -> JSONResponse:
        return run(client.health)

    return client
