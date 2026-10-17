"""Serve the built front-door application and its root-scoped PWA assets."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse


def register_static_routes(app: FastAPI, static_dir: str | os.PathLike[str] | None = None) -> None:
    root = Path(static_dir or os.environ.get("PW_STATIC_DIR") or Path(__file__).parents[1] / "static" / "app").resolve()

    def file_response(path: Path, media_type: str | None = None, headers: dict[str, str] | None = None):
        try:
            path.resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if not path.is_file():
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(path, media_type=media_type, headers=headers or {})

    @app.get("/sw.js")
    def service_worker():
        return file_response(root / "sw.js", "text/javascript", {"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

    @app.get("/manifest.webmanifest")
    def manifest():
        return file_response(root / "manifest.webmanifest", "application/manifest+json")

    @app.api_route("/{path:path}", methods=["POST", "PUT", "PATCH", "DELETE"])
    def no_such_write(path: str):
        # Registered last with the GET fallback: an unknown write is a plain 404, never a 405 from the SPA route.
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    @app.get("/{path:path}")
    def static_or_spa(path: str, request: Request):
        if path == "api" or path.startswith("api/") or path == "healthz":
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        raw = request.scope.get("raw_path", b"").lower()
        if b"%2e" in raw or "\\" in path or any(part == ".." for part in path.split("/")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if path.startswith("assets/"):
            return file_response(root / path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
        if "/" not in path:
            candidate = root / path
            if candidate.is_file():
                return file_response(candidate)
        index = root / "index.html"
        if not index.is_file():
            return JSONResponse({"detail": "UI not built"}, status_code=503)
        return file_response(index, "text/html", {"Cache-Control": "no-cache"})
