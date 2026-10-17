"""The Connect workshop API: try a request, preview a card. Owner-only, CSRF (principal dependency).

``POST /api/connect/try`` runs ONE read request through the confinement seam (never a write: writes are
tested through an approved action), with either a saved provider or an unsaved provider body, and returns
a scrubbed sample plus suggested fields. ``POST /api/connect/preview`` shows the C2 envelope an unsaved card
would produce from a sample (no network) or from a saved request. Nothing here saves anything: saving uses
the config CRUD. Every executed try is written to History without bodies, and tries are rate limited.

Unsaved providers carry a ``secret_ref`` only (the models have no field for a raw secret and reject extra
keys). Secret names that belong to Worlds itself (PW_*, OIDC_*, anything bootstrap) cannot be borrowed by an
unsaved provider: otherwise "try this URL" could send Worlds' own credentials to a host of the caller's choice.
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from typing import Any, Callable

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .authn import Principal
from .cards import CardService
from .config_store import ConfigStore, _describe
from .confinement import ConfinementError, RawResponse, confined_request
from .models import Card, Provider, Request, send_scoped
from .secrets import resolve_secret_ref
from .suggest import SAMPLE_BYTES, redact_sample, scrub_text, suggest_fields

TRY_LIMIT = 10          # tries per window
TRY_WINDOW_S = 60.0
MAX_PREVIEW_SAMPLE = 256 * 1024
_RESERVED_ENV = re.compile(r"^(PW_|OIDC_)|BOOTSTRAP", re.I)


def _http_class(status: int) -> str | None:
    if status in (401, 403):
        return "auth_failed"
    if 400 <= status < 500:
        return "http_4xx"
    if status >= 500 or status < 200 or status >= 300:
        return "http_5xx" if status >= 500 else "redirect_refused"
    return None


def _depth(node: Any, limit: int = 20, level: int = 0) -> bool:
    if level > limit:
        return False
    if isinstance(node, dict):
        return all(_depth(v, limit, level + 1) for v in node.values())
    if isinstance(node, list):
        return all(_depth(v, limit, level + 1) for v in node)
    return True


def register_connect_routes(
    app: FastAPI,
    store: ConfigStore,
    cards: CardService,
    *,
    owner: Callable[..., Principal],
    send: Callable[..., Any] = confined_request,
    audit: Callable[[str, dict, str], None] | None = None,
    clock: Callable[[], float] = time.time,
    secret_values: Callable[[], list[str]] = lambda: [],
) -> None:
    window: deque[float] = deque()

    def limited() -> int:
        now = clock()
        while window and now - window[0] >= TRY_WINDOW_S:
            window.popleft()
        if len(window) >= TRY_LIMIT:
            return int(TRY_WINDOW_S - (now - window[0])) + 1
        window.append(now)
        return 0

    def secrets_for(provider: Provider) -> list[str]:
        vals = list(secret_values())
        v = resolve_secret_ref(provider.auth.secret_ref) if provider.auth.secret_ref else None
        return vals + ([v] if v else [])

    def build_provider(spec: Any) -> tuple[Provider, bool]:
        if isinstance(spec, str):
            saved = store.get("provider", spec)
            if saved is None:
                raise HTTPException(status_code=404, detail="no such saved provider")
            return saved, True
        if not isinstance(spec, dict):
            raise HTTPException(status_code=422, detail="provider must be a saved provider id or a provider object")
        body = {"schema_version": 1, "id": "tryout", "name": "Try", "kind": "http", **spec}
        try:
            provider = Provider.model_validate(body)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=_describe(exc, "invalid provider")) from None
        ref = provider.auth.secret_ref or ""
        if ref.startswith("env:") and _RESERVED_ENV.search(ref[4:]):
            raise HTTPException(status_code=422, detail="that secret name belongs to Worlds itself and cannot be used to try a service")
        return provider, False

    def build_request(spec: Any, provider: Provider) -> Request:
        if not isinstance(spec, dict):
            raise HTTPException(status_code=422, detail="request must be an object")
        body = {"schema_version": 1, "method": "GET", **spec, "provider": provider.id}
        if not str(body.get("id", "")).startswith(provider.id + "."):
            body["id"] = f"{provider.id}.try"
        try:
            request = Request.model_validate(body)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=_describe(exc, "invalid request")) from None
        if request.resolved_effect() == "write":
            raise HTTPException(status_code=422, detail="test write actions through an approved action")
        return request

    @app.post("/api/connect/try")
    def try_request(body: dict = Body(...), p: Principal = Depends(owner)) -> JSONResponse:
        extra = set(body) - {"provider", "request"}
        if extra or "provider" not in body or "request" not in body:
            raise HTTPException(status_code=422, detail="send {provider, request}")
        provider, saved = build_provider(body["provider"])
        request = build_request(body["request"], provider)
        wait = limited()
        if wait:
            raise HTTPException(status_code=429, detail="too many tries; wait a moment", headers={"Retry-After": str(wait)})
        try:
            result = send_scoped(send, provider, request, effect="read")   # exactly one attempt, through confinement
        except Exception:
            result = ConfinementError("connection", "sender error")
        out = _describe_result(result, secrets_for(provider))
        if audit is not None:
            try:
                audit("connect_try", {"provider": provider.id, "saved": saved, "method": request.method, "path": request.path,
                                      "status_code": out["status_code"], "error_class": out["error_class"]}, p.id)
            except Exception:  # an audit failure must not hide the result, but it must not pass silently either
                out["audit"] = "not recorded"
        return JSONResponse(out, headers={"Cache-Control": "no-store"})

    @app.post("/api/connect/preview")
    def preview(body: dict = Body(...), p: Principal = Depends(owner)) -> JSONResponse:
        extra = set(body) - {"card", "sample", "request"}
        if extra or "card" not in body or ("sample" in body) == ("request" in body):
            raise HTTPException(status_code=422, detail="send {card, sample} or {card, request}")
        spec = body["card"]
        if not isinstance(spec, dict):
            raise HTTPException(status_code=422, detail="card must be an object")
        spec = {"schema_version": 1, "id": "preview", "title": "Preview", "meaning": {"concept": "preview", "short": "Preview"}, **spec}
        if not spec.get("request") and not spec.get("requests"):
            spec["request"] = "preview.sample"
        try:
            card = Card.model_validate(spec)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=_describe(exc, "invalid card")) from None
        if "sample" in body:
            sample = body["sample"]
            if len(json.dumps(sample, default=str)) > MAX_PREVIEW_SAMPLE or not _depth(sample):
                raise HTTPException(status_code=413, detail="that sample is too large")
            return JSONResponse(cards.preview(card, sample), headers={"Cache-Control": "no-store"})
        request_id = body["request"]
        if not isinstance(request_id, str) or store.get("request", request_id) is None:
            raise HTTPException(status_code=404, detail="no such saved request")
        if store.get("request", request_id).resolved_effect() == "write":
            raise HTTPException(status_code=422, detail="a card can only preview a read request")
        card = card.model_copy(update={"request": request_id, "requests": []})
        return JSONResponse(cards.build_for(card), headers={"Cache-Control": "no-store"})


def _describe_result(result: Any, secrets: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "status_code": None, "duration_ms": None, "error_class": None, "note": "",
                           "content_type": None, "sample": None, "truncated": False, "suggested_fields": []}
    if isinstance(result, ConfinementError):
        out.update(error_class=result.error_class, status_code=result.status_code, duration_ms=result.duration_ms,
                   note=scrub_text(result.note or "", secrets)[:300])
        return out
    if not isinstance(result, RawResponse):
        out.update(error_class="connection", note="the sender returned nothing usable")
        return out
    out.update(status_code=result.status_code, duration_ms=result.duration_ms,
               content_type=(result.headers.get("content-type") or "")[:100] or None)
    out["error_class"] = _http_class(result.status_code)
    out["ok"] = out["error_class"] is None
    raw = result.body
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        doc = None
    if isinstance(doc, (dict, list)):
        text = json.dumps(redact_sample(doc, secrets), indent=2, ensure_ascii=False)
        out["suggested_fields"] = suggest_fields(doc, secret_values=secrets) if out["ok"] else []
    else:
        if doc is None and raw:
            out["error_class"] = out["error_class"] or "malformed"
            out["ok"] = False if out["error_class"] == "malformed" else out["ok"]
        text = scrub_text(raw.decode("utf-8", errors="replace"), secrets)
    if len(text.encode()) > SAMPLE_BYTES:
        text, out["truncated"] = text.encode()[:SAMPLE_BYTES].decode("utf-8", errors="ignore"), True
    out["sample"] = text
    return out
