"""Web Push and notification routes for the front-door application (Rylee, 2026-10-08: the new interface keeps
notifications and the PWA).

Reuses :mod:`personal_world.push` as-is: VAPID, the subscription and notification stores, quiet hours, tiers,
dedupe and the per-caller rate limit. Worlds is single-owner here, so every route stores and sends for the fixed
person id ``owner``. Subscription endpoints and keys never leave the store in a response.
"""
from __future__ import annotations

import re
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request

from .. import push
from .authn import Principal

_SOURCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")


def register_push_routes(app: FastAPI, hub: push.PushHub, *, owner: Callable, anyone: Callable) -> None:
    @app.get("/api/push/public-key")
    def public_key(p: Principal = Depends(owner)):
        key = hub.public_key()
        if not key or not hub.configured():
            raise HTTPException(409, "push is not configured on this server")
        return {"ok": True, "data": {"public_key": key}}

    @app.post("/api/push/subscriptions")
    async def subscribe(request: Request, p: Principal = Depends(owner)):
        body = await request.json()
        try:
            sid, created = hub.add_subscription("owner", body.get("subscription") or {}, str(body.get("device_label") or ""))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"ok": True, "data": {"id": sid, "created": created}}

    @app.get("/api/push/subscriptions")
    def subscriptions(p: Principal = Depends(owner)):
        return {"ok": True, "data": hub.list_subscriptions("owner")}

    @app.delete("/api/push/subscriptions/{sub_id}")
    def delete_subscription(sub_id: str, p: Principal = Depends(owner)):
        if not hub.remove_subscription("owner", sub_id):
            raise HTTPException(404, "no such device")
        return {"ok": True, "data": {"id": sub_id, "removed": True}}

    @app.get("/api/notifications")
    def notifications(request: Request, p: Principal = Depends(owner)):
        unread = request.query_params.get("unread", "") in ("1", "true", "yes")
        try:
            limit = int(request.query_params.get("limit") or 20)
        except ValueError as exc:
            raise HTTPException(422, "limit must be a number") from exc
        return {"ok": True, "data": hub.list_notifications("owner", unread, limit)}

    @app.post("/api/notifications/{note_id}/read")
    def mark_read(note_id: str, p: Principal = Depends(owner)):
        if not hub.mark_read("owner", note_id):
            raise HTTPException(404, "no such notification")
        return {"ok": True, "data": {"id": note_id, "read": True}}

    @app.post("/api/notifications/read-all")
    def read_all(p: Principal = Depends(owner)):
        return {"ok": True, "data": {"read": hub.read_all("owner")}}

    @app.get("/api/notifications/prefs")
    def prefs(p: Principal = Depends(owner)):
        return {"ok": True, "data": hub.get_prefs("owner")}

    @app.put("/api/notifications/prefs")
    async def put_prefs(request: Request, p: Principal = Depends(owner)):
        try:
            return {"ok": True, "data": hub.put_prefs("owner", await request.json())}
        except push.PrefsError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/notifications/test")
    def test_push(p: Principal = Depends(owner)):
        return {"ok": True, "data": hub.test_push("owner")}

    @app.post("/api/notify")
    async def notify(request: Request, principal: Principal = Depends(anyone)):
        # The owner may notify themselves; an agent token needs the `notify` scope. Either way the one owner is the
        # recipient: there is no `to`.
        if principal.kind == "agent" and not principal.allows_scope("notify"):
            raise HTTPException(403, "the notify scope is required to publish")
        body = await request.json()
        tier, source = body.get("tier"), body.get("source")
        title, content = body.get("title"), body.get("body")
        if tier not in push.TIERS:
            raise HTTPException(422, "tier is good_news, update or when_ready")
        if not isinstance(source, str) or not _SOURCE.fullmatch(source):
            raise HTTPException(422, "source is a short plain id")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise HTTPException(422, "title is needed (max 120)")
        if not isinstance(content, str) or not 1 <= len(content.strip()) <= 4000:
            raise HTTPException(422, "body is needed (max 4000)")
        try:
            link = push.valid_same_origin_link(body.get("link"))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        dedupe = body.get("dedupe_key")
        if dedupe is not None and (not isinstance(dedupe, str) or len(dedupe) > 120):
            raise HTTPException(422, "dedupe_key must be at most 120 characters")
        private = body.get("private", False)
        if not isinstance(private, bool):
            raise HTTPException(422, "private must be a boolean")
        caller = f"{principal.kind}:{principal.id}"
        if hub.rate_limited(caller):
            raise HTTPException(429, "too many notifications this minute; wait a moment")
        try:
            result = hub.notify("owner", tier=tier, source=source, title=title.strip(), body=content.strip(),
                                link=link, dedupe_key=dedupe, private=private)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"ok": True, "data": result}
