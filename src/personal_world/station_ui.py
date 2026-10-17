"""Same-origin serving for the Project Worlds interface.

Owner decision, 2026-09-22: the React rebuild IS the interface. It is
served at ``/`` — the primary path — and there is exactly one. The
predecessor vanilla Station is retired: not mounted, not packaged, not
shipped. Old paths (``/station/*``, ``/vnext/*``) redirect to ``/`` so
bookmarks land on the product instead of a 404.

Serving it from this process — rather than a separate static host — is
what makes the browser session work: the ``pw_session`` cookie is
same-origin, so every ``fetch`` the UI makes carries credentials with no
CORS exception anywhere, and the API needs no browser-only token path.

Boundaries this module keeps:

* **Authorization reuses the canonical entry point.** Nothing here re-implements
  a credential check: ``api.require_auth`` decides, and this module only
  maps its verdict onto a browser-appropriate response (a redirect to
  ``/login``) instead of a JSON 401.
* **First-run wins.** Before the ``setup-complete`` marker exists, every
  interface path redirects to ``/setup``; a half-built world is never
  presented as a working one.
* **No user-controlled filesystem paths.** The served set is an allowlist
  built once at app start: a relative POSIX path → a resolved absolute
  ``Path``. Traversal cannot escape because it simply misses the dict.
  Newly added files are picked up on restart; edited files are re-read
  per request and revalidated by ETag.
* **Reserved namespaces stay 404, never HTML.** An unknown path under
  ``/api`` or ``/static`` answers JSON 404 like any unrouted API call —
  the SPA fallback never swallows a namespace it does not own.
* **Only web assets, never documentation.** ``.md`` files are excluded on
  purpose; ``_``-prefixed directories stay out entirely.
* **absence.** When the build is not staged, ``/`` says so plainly
  (503) with the operator's actual fix, and never echoes a filesystem
  path. The container image builds the UI itself, so a missing build
  means a broken image build, not a silent hole.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.responses import Response

_logger = logging.getLogger("personal_world.station_ui")

#: Web assets the interface may serve. Anything else (notably ``.md``
#: internal notes) is not part of the UI and is never served.
SERVED_SUFFIXES = frozenset(
    {
        ".html",
        ".css",
        ".js",
        ".mjs",
        ".json",
        ".webmanifest",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".woff",
        ".woff2",
        ".txt",
    }
)

#: Explicit types for the text assets that must not be sniffed wrong.
#: Anything unlisted falls through to Starlette's mimetype guess.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
}

#: Directory segments that are never served (archives, tooling, dotdirs).
SKIPPED_PREFIXES = ("_", ".")

#: First path segments owned by the API/server, never by the SPA. An
#: unknown path under one of these answers JSON 404, not index.html.
RESERVED_TOP_LEVEL = frozenset(
    {
        "api",
        "login",
        "invite",
        "logout",
        "setup",
        "healthz",
        "static",
        "openapi.json",
        "docs",
        "redoc",
        # server-owned asset namespaces (allowlisted art/sprites): a miss
        # there is a 404, never a silently served SPA shell
        "today",
        "companions",
        "icons",
    }
)

#: Report-only Content-Security-Policy for the interface page. It blocks
#: nothing: browsers log what a stricter policy would refuse, so a real
#: policy can be tightened from evidence. ``style-src`` allows inline
#: styles because the interface sets some through the ``style`` attribute.
CSP_REPORT_ONLY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

#: Retired interface paths. They redirect to / so nothing ever 404s on a
#: bookmark — and so the old surfaces are unreachable, not just unlinked.
LEGACY_PREFIXES = ("station", "vnext")


def default_app_dir() -> Path:
    """Where the built interface lives: ``static/app``, or
    ``PW_APP_DIST`` when a deployment stages it elsewhere (tests use the
    override)."""
    override = os.environ.get("PW_APP_DIST")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "static" / "app"


def build_allowlist(root: Path) -> dict[str, Path]:
    """Map every servable relative path under ``root`` to its file.

    Built once, eagerly, so a request never turns a user-supplied string
    into a filesystem lookup.
    """
    allowlist: dict[str, Path] = {}
    if not root.is_dir():
        return allowlist
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(root)
        if any(part.startswith(SKIPPED_PREFIXES) for part in relative.parts):
            continue
        if candidate.suffix.lower() not in SERVED_SUFFIXES:
            continue
        allowlist[relative.as_posix()] = candidate.resolve()
    return allowlist


APP_NOT_INSTALLED_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Project Worlds — interface not built</title></head>
<body>
<main id="main-content">
<h1>The interface is not built here</h1>
<p>This Project Worlds instance has no interface build staged, so there is
nothing to show. The API is running normally; nothing else is affected.</p>
<p>Operator details: the container image builds the interface itself, so a
fresh <code>docker compose build</code> fixes a broken image. For a source
checkout, run <code>npm ci &amp;&amp; npm run build</code> in <code>ui/</code>
and then <code>bash scripts/build-app.sh</code> to stage it, and restart.</p>
</main>
</body>
</html>"""


def app_router(data_dir: Path, dist: Path | None = None) -> APIRouter:
    """Build the interface router. Mount it LAST so it never shadows a
    real route.

    ``data_dir`` supplies the first-run marker; ``dist`` overrides the
    build directory (tests, or a deployment that stages the build
    elsewhere).
    """
    root = (dist or default_app_dir()).resolve()
    allowlist = build_allowlist(root)
    if not allowlist:
        _logger.warning(
            "interface build not installed (%s); / will report that "
            "instead of serving the app",
            root.name or "unset",
        )

    router = APIRouter()
    data_dir = Path(data_dir)

    async def _gate(request: Request) -> Response | None:
        from .api import require_auth  # local import: api.py mounts us

        if not (data_dir / "setup-complete").exists():
            return RedirectResponse(url="/setup", status_code=303)
        try:
            await require_auth(request)
        except HTTPException:
            return RedirectResponse(url="/login", status_code=303)
        return None

    def _index(request: Request) -> Response:
        from .api import _cached_file

        path = allowlist.get("index.html")
        if path is None or not path.is_file():
            return HTMLResponse(
                APP_NOT_INSTALLED_HTML,
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        response = _cached_file(request, path, CONTENT_TYPES[".html"])
        response.headers["Content-Security-Policy-Report-Only"] = CSP_REPORT_ONLY
        return response

    def _file(request: Request, rel: str) -> Response:
        from .api import _cached_file

        path = allowlist[rel]
        ctype = CONTENT_TYPES.get(path.suffix.lower())
        return _cached_file(request, path, ctype)

    # --- retired paths: redirect, never serve --------------------------
    @router.get("/station", include_in_schema=False)
    @router.get("/station/", include_in_schema=False)
    @router.get("/vnext", include_in_schema=False)
    @router.get("/vnext/", include_in_schema=False)
    async def _retired_root(request: Request):
        return RedirectResponse(url="/", status_code=307)

    @router.get("/station/{rest:path}", include_in_schema=False)
    @router.get("/vnext/{rest:path}", include_in_schema=False)
    async def _retired_deep(rest: str, request: Request):
        return RedirectResponse(url="/", status_code=307)

    # --- the interface itself ------------------------------------------
    @router.get("/", include_in_schema=False)
    async def interface_root(request: Request):
        blocked = await _gate(request)
        if blocked is not None:
            return blocked
        return _index(request)

    # --- assets and SPA fallback (must come last) ----------------------
    @router.get("/{full_path:path}", include_in_schema=False)
    async def interface_asset(full_path: str, request: Request):
        top = full_path.split("/", 1)[0]
        if top in RESERVED_TOP_LEVEL:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        path = allowlist.get(full_path)
        if path is not None and path.is_file():
            return _file(request, full_path)
        # React SPA: any other unknown path is client-side routing —
        # serve index so deep links work. A missing build still reports
        # through _index.
        blocked = await _gate(request)
        if blocked is not None:
            return blocked
        return _index(request)

    return router
