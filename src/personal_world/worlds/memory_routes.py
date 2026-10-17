"""HTTP routes for Memory (C4): Kept, Later, Records, History, Find, export and backup.

Everything here is OWNER-only (a session; CSRF on writes comes from the principal dependency) except
``GET /api/memory/agent/{name}``, the one narrow, scoped, logged read an agent token may make. Locked
records need the owner's fresh step-up on the SESSION: the gate is ``principal.has_step_up()``, never a
client-supplied flag, and a token never has it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from .authn import Principal
from .memory_store import Locked, MemoryError_, MemoryStore, NotFound, NotPermitted_

_FIELDS = ("title", "body", "tags", "due_at", "kind", "sensitivity", "status")


def register_memory_routes(app: FastAPI, memory: MemoryStore, backup_dir: str | Path, *,
                           anyone: Callable[..., Principal], owner: Callable[..., Principal],
                           clock: Callable[[], float]) -> None:
    def stepped(p: Principal) -> bool:
        return p.has_step_up(clock()) is True

    def guard(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except Locked:
            raise HTTPException(status_code=403, detail="step_up_required") from None
        except NotFound:
            raise HTTPException(status_code=404, detail="not found") from None
        except NotPermitted_ as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except MemoryError_ as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    # ---- fixed paths first so "find" is never taken for a table name

    @app.get("/api/memory/find")
    def find(q: str = Query("", max_length=500), limit: int = Query(20), p: Principal = Depends(owner)) -> list[dict]:
        return guard(lambda: memory.find(q, step_up=stepped(p), agent=False, limit=limit))

    @app.get("/api/memory/history")
    def history(limit: int = Query(50), before_id: int | None = Query(None), p: Principal = Depends(owner)) -> list[dict]:
        return guard(lambda: memory.history(limit=limit, before_id=before_id))

    @app.get("/api/memory/export/{table}")
    def export(table: str, p: Principal = Depends(owner)) -> StreamingResponse:
        lines = guard(lambda: memory.export_ndjson(table, step_up=stepped(p), actor=p.id))
        return StreamingResponse(lines, media_type="application/x-ndjson",
                                 headers={"Content-Disposition": f'attachment; filename="worlds-{table}.ndjson"',
                                          "Cache-Control": "no-store"})

    @app.post("/api/memory/backup")
    def backup(p: Principal = Depends(owner)) -> dict:
        path = guard(lambda: memory.backup(backup_dir, actor=p.id))
        return {"file": path.name}

    @app.get("/api/memory/agent/{name}")
    def agent(name: str, p: Principal = Depends(anyone)) -> dict:
        scopes = ("memory.*",) if p.is_owner else p.scopes
        return guard(lambda: memory.agent_answer(name, scopes=scopes, actor=p.id))

    # ---- the three tables (owner only)

    @app.get("/api/memory/{table}")
    def list_rows(table: str, status: str | None = Query(None), limit: int = Query(50), offset: int = Query(0),
                  p: Principal = Depends(owner)) -> list[dict]:
        return guard(lambda: memory.list(table, step_up=stepped(p), status=status, limit=limit, offset=offset))

    @app.post("/api/memory/{table}")
    def create(table: str, body: dict = Body(...), p: Principal = Depends(owner)) -> dict:
        allowed = (set(_FIELDS) - {"status"}) | {"provenance", "source_ref"}   # a new later row is always open
        extra = set(body) - allowed
        if extra:
            raise HTTPException(status_code=400, detail=f"unknown fields: {sorted(extra)}")
        if "title" not in body:
            raise HTTPException(status_code=400, detail="title is required")
        kwargs = {k: body[k] for k in allowed if k in body}
        return guard(lambda: memory.add(table, actor=p.id, **kwargs))

    @app.get("/api/memory/{table}/{row_id}")
    def get_row(table: str, row_id: str, p: Principal = Depends(owner)) -> dict:
        return guard(lambda: memory.get(table, row_id, step_up=stepped(p), actor=p.id))

    @app.patch("/api/memory/{table}/{row_id}")
    def patch_row(table: str, row_id: str, body: dict = Body(...), p: Principal = Depends(owner)) -> dict:
        return guard(lambda: memory.update(table, row_id, body, actor=p.id, step_up=stepped(p)))

    @app.delete("/api/memory/{table}/{row_id}")
    def delete_row(table: str, row_id: str, p: Principal = Depends(owner)) -> dict:
        guard(lambda: memory.delete(table, row_id, actor=p.id, step_up=stepped(p)))
        return {"ok": True}
