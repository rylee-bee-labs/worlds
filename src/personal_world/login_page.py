"""Server-rendered sign-in page — the Station-only cutover.

The Station is the product UI, but it has no sign-in view of its own; the
backend's ``station_ui`` redirects an unauthenticated visitor to ``/login``.
Previously ``/login`` was served by the superseded React SPA. This module
replaces that with a tiny, dependency-free page that posts to the existing
``POST /api/auth/login`` (which owns the session cookie) and links to OIDC
when the operator has configured it.

Additive and : before first-run completes it sends the visitor to
``/setup``; if the static file is missing it answers 503 rather than a
fabricated page. No secret is ever embedded here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from .setup_wizard import setup_needed

_LOGIN_HTML = Path(__file__).parent / "static" / "login" / "index.html"


def register_login_page(app: FastAPI, *, data_dir: Path) -> None:
    """Mount ``GET /login`` (and the trailing-slash form). Additive; must be
    registered before any catch-all route."""
    data_dir = Path(data_dir)

    def _page() -> Any:
        if setup_needed(data_dir):
            return RedirectResponse("/setup", status_code=303)
        if not _LOGIN_HTML.is_file():
            raise HTTPException(status_code=503, detail="login page missing")
        return FileResponse(
            _LOGIN_HTML,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/login", include_in_schema=False)
    async def login_page() -> Any:
        return _page()

    @app.get("/login/", include_in_schema=False)
    async def login_page_slash() -> Any:
        return RedirectResponse("/login", status_code=303)
