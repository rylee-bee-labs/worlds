"""Server-rendered invite accept page — signed-out, like ``/login``.

People screens step 2 handoff: an invite link is ``/invite#<code>``.
The code lives in the URL **fragment**, which never reaches the server,
so this page is static and unauthenticated by design: it reads the
fragment in the browser and posts it to the existing
``POST /api/invites/accept`` (the one-time token is the proof; there is
no session behind this route). The sign-in key that accept returns is
shown once and this page never writes it to a URL, to browser storage,
or to any log.

Additive and : before first-run completes it sends the visitor
to ``/setup``; if the static file is missing it answers 503 rather than
a fabricated page. The serving pattern is copied from ``login_page.py``
(file, media type, ``Cache-Control: no-store``, trailing-slash redirect,
``include_in_schema=False`` — pages are not part of the API Lego box).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from .setup_wizard import setup_needed

_INVITE_HTML = Path(__file__).parent / "static" / "invite" / "index.html"


def register_invite_page(app: FastAPI, *, data_dir: Path) -> None:
    """Mount ``GET /invite`` (and the trailing-slash form). Additive; must
    be registered before any catch-all route."""
    data_dir = Path(data_dir)

    def _page() -> Any:
        if setup_needed(data_dir):
            return RedirectResponse("/setup", status_code=303)
        if not _INVITE_HTML.is_file():
            raise HTTPException(status_code=503, detail="invite page missing")
        return FileResponse(
            _INVITE_HTML,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/invite", include_in_schema=False)
    async def invite_page() -> Any:
        return _page()

    @app.get("/invite/", include_in_schema=False)
    async def invite_page_slash() -> Any:
        return RedirectResponse("/invite", status_code=303)
