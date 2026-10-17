"""The Companion connector: a confined, whitelisting proxy to the private Companion service (spec slice 7).

Worlds is public and Companion is private, so nothing here names a Companion address, persona or thread. The
service is an ordinary C1 provider with id ``companion`` in the owner's config: its address and its bearer token
(``auth.secret_ref: file:PW_COMPANION_TOKEN_FILE``, a mounted file) never reach the browser. Every call goes through
:func:`confined_request` (LAN allowed only because the provider says ``network.lan: true``; same deadline and size caps).

Rules this module keeps:

* **Whitelist, both ways.** A request is rebuilt from the few fields the spec allows; a response is rebuilt the same
  way. Anything else (in particular a stored turn's ``context_items`` and ``context_canaries``) is dropped, never forwarded.
* **No second chat store.** Nothing is written anywhere. Only counts are logged, never message text.
* **Unknown is an answer.** An unreachable, refusing or unauthorized Companion is :class:`Unavailable`, which the route
  turns into an honest "Companion isn't answering", never a made-up reply.
* **Worlds never decides a grant.** Grant routes forward a request and show state; approval happens in Project Home.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from urllib.parse import quote

from .confinement import ConfinementError, RawResponse, confined_request
from .models import send_scoped

logger = logging.getLogger("personal_world.worlds.companion")

PROVIDER_ID = "companion"

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MSG_ID = re.compile(r"^[A-Za-z0-9_-]{8,100}$")
_WORD = re.compile(r"^[a-z][a-z_]{0,23}$")
MAX_MESSAGE = 8000
MAX_CURSOR = 200
TIERS = ("ordinary", "stepped")
GRANT_STATES = ("pending", "active", "denied", "expired", "revoked")

Reason = Literal["not_configured", "unauthorized", "timeout", "unreachable", "refused", "unreadable"]


class NotConfigured(Exception):
    """No ``companion`` provider (or no token) in the owner's config."""


class BadInput(ValueError):
    """The browser sent something outside the whitelist."""


class Unavailable(Exception):
    """Companion did not give a usable answer. ``reason`` is a fixed word, never upstream text."""

    def __init__(self, reason: Reason, status: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status = status


# ------------------------------------------------------------------ small cleaners


def _str(value: Any, limit: int, *, allow_empty: bool = True) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.replace("\x00", "")
    if not allow_empty and not value.strip():
        return None
    return value[:limit]


def _int(value: Any, lo: int, hi: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if lo <= value <= hi else None


def _strings(value: Any, *, count: int = 50, limit: int = 300) -> list[str]:
    if not isinstance(value, list):
        return []
    return [s for s in (_str(x, limit) for x in value[:count]) if s is not None]


def _safe_link(value: Any) -> str | None:
    """Only a relative or http(s) link survives (the browser opens these)."""
    s = _str(value, 500)
    if not s:
        return None
    s = s.strip()
    if s.startswith("/") and not s.startswith("//"):
        return s
    return s if re.match(r"^https?://[^\s]+$", s) else None


# ------------------------------------------------------------------ requests (browser -> Companion)


def clean_turn_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BadInput("a turn is an object")
    message = _str(payload.get("message"), MAX_MESSAGE + 1, allow_empty=False)
    if message is None:
        raise BadInput("message is required")
    if len(message) > MAX_MESSAGE:
        raise BadInput(f"message is too long (limit {MAX_MESSAGE} characters)")
    cmid = payload.get("client_msg_id")
    if not isinstance(cmid, str) or not _MSG_ID.match(cmid):
        raise BadInput("client_msg_id is required (8 to 100 letters, digits, - or _)")
    out: dict[str, Any] = {"message": message, "client_msg_id": cmid}
    tid = payload.get("thread_id")
    if tid is not None:
        if not isinstance(tid, str) or not _ID.match(tid):
            raise BadInput("thread_id is not valid")
        out["thread_id"] = tid
    ui = payload.get("ui_context")
    if ui is not None:
        if not isinstance(ui, dict):
            raise BadInput("ui_context is an object")
        clean: dict[str, Any] = {}
        if isinstance(ui.get("quiet"), bool):
            clean["quiet"] = ui["quiet"]
        items = ui.get("items")
        if isinstance(items, list):
            # Only the text. A browser never sets a source, class or tier for what Companion sees.
            texts = [t for t in (_str(i.get("text"), 400) if isinstance(i, dict) else None for i in items[:10]) if t]
            if texts:
                clean["items"] = [{"text": t} for t in texts]
        if clean:
            out["ui_context"] = clean
    return out


def clean_grant_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BadInput("a grant request is an object")
    ttl = _int(payload.get("ttl_s"), 60, 3600)
    reason = _str(payload.get("reason"), 300, allow_empty=False)
    if ttl is None or reason is None:
        raise BadInput("ttl_s (60 to 3600) and reason are required")
    return {"tier": "stepped", "ttl_s": ttl, "reason": reason}


def clean_id(value: Any) -> str:
    if not isinstance(value, str) or not _ID.match(value):
        raise BadInput("not a valid id")
    return value


# ------------------------------------------------------------------ responses (Companion -> browser)


def _presentation(value: Any) -> dict[str, Any] | None:
    """The five semantic keys, as words. Anything else is dropped; the browser degrades unknown words itself."""
    if not isinstance(value, dict):
        return None
    out: dict[str, Any] = {}
    for key in ("v", "state", "tone", "gesture"):
        s = value.get(key)
        if isinstance(s, str) and (_WORD.match(s) or (key == "v" and re.match(r"^presentation/[0-9]{1,3}$", s))):
            out[key] = s
    if isinstance(value.get("speaking"), bool):
        out["speaking"] = value["speaking"]
    return out or None


def _grant(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    state = value.get("state")
    if state not in GRANT_STATES:
        return None
    return {"state": state, "expires_at": _str(value.get("expires_at"), 40)}


def clean_turn_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise Unavailable("unreadable")
    reply = _str(data.get("reply"), 20000)
    if reply is None:
        raise Unavailable("unreadable")
    sections = data.get("sections")
    return {
        "thread_id": _str(data.get("thread_id"), 64),
        "reply": reply,
        "connection": _str(data.get("connection"), 80) or "",
        "tier_sent": data.get("tier_sent") if data.get("tier_sent") in TIERS else "stepped",   # fail closed: unknown reads as the higher tier
        "sections": {k[:40]: v for k, v in list(sections.items())[:12] if isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v >= 0} if isinstance(sections, dict) else {},
        "unknown": _strings(data.get("unknown")),
        "grant": _grant(data.get("grant")),
        "audit_id": _str(data.get("audit_id"), 100) or "",
        "presentation": _presentation(data.get("presentation")),
    }


def clean_threads_response(data: Any) -> dict[str, Any]:
    ids = data.get("threads") if isinstance(data, dict) else None
    return {"threads": [i for i in (ids if isinstance(ids, list) else [])[:200] if isinstance(i, str) and _ID.match(i)]}


def clean_thread_response(data: Any) -> dict[str, Any]:
    """Turns carry only text, time and tier. ``context_items`` and ``context_canaries`` are never forwarded."""
    if not isinstance(data, dict) or not isinstance(data.get("turns"), list):
        raise Unavailable("unreadable")
    turns = []
    for t in data["turns"][:500]:
        if not isinstance(t, dict):
            continue
        turns.append({
            "ts": _str(t.get("ts"), 40),
            "visibility_tier": t.get("visibility_tier") if t.get("visibility_tier") in TIERS else "stepped",
            "user_text": _str(t.get("user_text"), 20000) or "",
            "assistant_text": _str(t.get("assistant_text"), 20000) or "",
            "client_msg_id": _str(t.get("client_msg_id"), 100),
        })
    tid = _str(data.get("thread_id"), 64)
    return {"thread_id": tid, "turns": turns}


def _item(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    text = _str(value.get("text"), 500)
    if text is None:
        return None
    return {
        "text": text,
        "source": _str(value.get("source"), 80) or "",
        "when": _str(value.get("when"), 40),
        "cls": _str(value.get("cls"), 24) or "",
        "tier": value.get("tier") if value.get("tier") in TIERS else "stepped",
    }


def clean_context_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise Unavailable("unreadable")

    def items(key: str) -> list[dict[str, Any]]:
        raw = data.get(key)
        return [i for i in (_item(x) for x in (raw if isinstance(raw, list) else [])[:50]) if i is not None]

    return {
        "tier": data.get("tier") if data.get("tier") in TIERS else "stepped",
        "budget_chars": _int(data.get("budget_chars"), 0, 1_000_000),
        "used_chars": _int(data.get("used_chars"), 0, 1_000_000),
        "reviewed": items("reviewed"), "working": items("working"), "recall": items("recall"), "live": items("live"),
        "unknown": _strings(data.get("unknown")),
    }


def clean_changes_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise Unavailable("unreadable")
    changes = []
    for c in (data.get("changes") if isinstance(data.get("changes"), list) else [])[:100]:
        if not isinstance(c, dict) or c.get("kind") not in ("new", "gone"):
            continue
        changes.append({
            "source": _str(c.get("source"), 40) or "",
            "id": _str(c.get("id"), 120) or "",
            "kind": c["kind"],
            "title": _str(c.get("title"), 300) or "",
            "link": _safe_link(c.get("link")),
            "observed_at": _str(c.get("observed_at"), 40),
        })
    return {"cursor": _str(data.get("cursor"), MAX_CURSOR), "changes": changes, "unknown": _strings(data.get("unknown"))}


def clean_grant_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise Unavailable("unreadable")
    state = data.get("state")
    return {
        "grant_id": _str(data.get("grant_id") or data.get("id"), 100),
        "state": state if state in GRANT_STATES else "unknown",
        "expires_at": _str(data.get("expires_at"), 40),
        "approval_id": _str(data.get("approval_id"), 100),
        "link": _safe_link(data.get("link")),
    }


def clean_health_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise Unavailable("unreadable")

    def states(value: Any, allowed: tuple[str, ...]) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {k[:24]: v for k, v in list(value.items())[:12] if isinstance(k, str) and v in allowed}

    return {
        "status": data.get("status") if data.get("status") == "ok" else "unknown",
        "commit": _str(data.get("commit"), 40) or "",
        "sources": states(data.get("sources"), ("ok", "unavailable")),
        "models": states(data.get("models"), ("healthy", "unavailable")),
    }


# ------------------------------------------------------------------ the client


@dataclass(frozen=True)
class _ProxyRequest:
    """What confinement needs to send one call. Not a C1 Request: query values here are the person's own text,
    so they are sent as written (``render_templates`` False) and never read as ``{today}``-style templates."""

    id: str
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None
    timeout_s: float | None = None
    render_templates: bool = False

    def resolved_effect(self) -> Literal["read", "write"]:
        return "read" if self.method in ("GET", "HEAD") else "write"


class Companion:
    """One confined call at a time. ``store`` supplies the ``companion`` provider (address and token reference)."""

    def __init__(self, store: Any, send: Callable[..., Any] = confined_request):
        self._store = store
        self._send = send

    def _provider(self) -> Any:
        try:
            provider = self._store.get("provider", PROVIDER_ID)
        except Exception:
            provider = None
        if provider is None:
            raise NotConfigured("no companion provider is configured")
        return provider

    def call(self, op: str, method: str, path: str, *, query: dict[str, str] | None = None, body: Any = None) -> Any:
        """Return the parsed JSON, or raise :class:`Unavailable` with a fixed reason."""
        provider = self._provider()
        request = _ProxyRequest(id=f"{PROVIDER_ID}.{op}", method=method, path=path, query=query or {}, body=body)
        # A missing token must not become an unauthenticated call that looks like a refusal.
        if provider.auth.type != "none":
            from .secrets import resolve_secret_ref

            if not resolve_secret_ref(provider.auth.secret_ref):
                raise NotConfigured("the companion token is not available")
        try:
            result = send_scoped(self._send, provider, request, effect=request.resolved_effect())
        except Exception:  # the sender's contract is never to raise; if it does, that is unknown, not a crash
            raise Unavailable("unreachable") from None
        if isinstance(result, ConfinementError):
            reason: Reason = "timeout" if result.error_class == "timeout" else "unauthorized" if result.error_class == "auth_failed" else "unreachable"
            raise Unavailable(reason)
        assert isinstance(result, RawResponse)
        status = result.status_code
        if status in (401, 403):
            raise Unavailable("unauthorized", status)
        if status == 501:
            raise Unavailable("refused", status)       # e.g. grants before the step-up slice exists
        if status >= 500:
            raise Unavailable("unreachable", status)
        if status >= 400:
            raise Unavailable("refused", status)
        try:
            return json.loads(result.body.decode("utf-8"))
        except Exception:
            raise Unavailable("unreadable", status) from None

    # --- the operations (each returns an already-whitelisted dict) ---

    def turn(self, payload: Any) -> dict[str, Any]:
        req = clean_turn_request(payload)
        out = clean_turn_response(self.call("turn", "POST", "/v1/turn", body=req))
        # Counts only: never the message, the reply or any context text.
        logger.info("companion turn: message_chars=%d reply_chars=%d unknown_lines=%d", len(req["message"]), len(out["reply"]), len(out["unknown"]))
        return out

    def threads(self) -> dict[str, Any]:
        return clean_threads_response(self.call("threads", "GET", "/v1/threads"))

    def thread(self, thread_id: str, after: int = 0) -> dict[str, Any]:
        tid = clean_id(thread_id)
        if _int(after, 0, 1_000_000) is None:
            raise BadInput("after is not valid")
        return clean_thread_response(self.call("thread", "GET", f"/v1/threads/{quote(tid)}", query={"after": str(after)}))

    def context(self, q: str = "") -> dict[str, Any]:
        text = _str(q, 500) or ""
        return clean_context_response(self.call("context", "GET", "/v1/context", query={"q": text}))

    def changes(self, since: str | None = None) -> dict[str, Any]:
        query = {"since": since[:MAX_CURSOR]} if isinstance(since, str) and since else {}
        return clean_changes_response(self.call("changes", "GET", "/v1/changes", query=query))

    def create_grant(self, payload: Any) -> dict[str, Any]:
        return clean_grant_response(self.call("grants-create", "POST", "/v1/grants", body=clean_grant_request(payload)))

    def grant(self, grant_id: str) -> dict[str, Any]:
        return clean_grant_response(self.call("grants-get", "GET", f"/v1/grants/{quote(clean_id(grant_id))}"))

    def revoke_grant(self, grant_id: str) -> dict[str, Any]:
        return clean_grant_response(self.call("grants-delete", "DELETE", f"/v1/grants/{quote(clean_id(grant_id))}"))

    def health(self) -> dict[str, Any]:
        return clean_health_response(self.call("health", "GET", "/health"))
