"""room/0 adapter: a Play-Nice room becomes Worlds cards, needs and action candidates.

A room (contracts/surfaces/ROOM.md) already speaks a shared shape, so this is a MAPPING, not per-card
config. Everything a room says is untrusted input: it is validated here, links must be same-origin
paths (rule 6), an unknown tone reads as ``update`` (rule 4), an unknown autonomy reads as
``ask_first``, and a card that cannot be read honestly becomes a ``degraded`` card with every value
``unknown`` rather than a made-up one. Network access happens only through the confinement seam
(``send``); Worlds speaks for one named person via the provider's validated ``principal_id``.

Mapping of the room descriptor status to a Worlds state: healthy -> healthy, degraded -> degraded,
unhealthy -> needs_attention (the room reports a problem the owner can act on), unknown -> unknown.
An unreachable room is ``unavailable`` with its last-known cards shown stale (rule 12).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from typing import Any, Callable
from urllib.parse import quote

from .config_store import ConfigInvalid
from .confinement import ConfinementError, RawResponse, confined_request
from .models import Action, Provider, Request, send_scoped

log = logging.getLogger(__name__)

STATE_FOR_STATUS = {"healthy": "healthy", "degraded": "degraded", "unhealthy": "needs_attention", "unknown": "unknown"}
STATE_FOR_ERROR = {"timeout": "unavailable", "connection": "unavailable", "http_5xx": "unavailable", "redirect_refused": "unavailable",
                   "too_large": "unavailable", "confinement_denied": "unavailable", "auth_failed": "needs_attention",
                   "http_4xx": "degraded", "malformed": "degraded"}
TONES = ("good_news", "update", "when_ready")
AUTONOMIES = ("auto", "check_in", "ask_first")
_ICON = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_MAX_CARDS, _MAX_NEEDS, _MAX_ACTIONS = 100, 50, 100
# Typed action input is bounded at the boundary (untrusted room JSON): at most 20 offered choices,
# each value/label trimmed to 120 characters, duplicates collapsed. State the numbers here, once.
_MAX_CHOICES, _MAX_CHOICE_VALUE, _MAX_CHOICE_LABEL = 20, 120, 120


# ----------------------------------------------------------------------- pure parsing

def slug(text: str, limit: int = 24) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-")
    return out or "x"


def room_card_id(provider_id: str, room_id: str) -> str:
    """A stable Worlds card id for a room card: valid under the C1 id pattern, unique per room card."""
    digest = hashlib.sha256(f"{provider_id}\0{room_id}".encode()).hexdigest()[:6]
    return f"{card_prefix(provider_id)}{slug(room_id, 22)}-{digest}"[:63].rstrip("-")


def card_prefix(provider_id: str) -> str:
    """The prefix every room card id of this provider starts with (same builder as room_card_id)."""
    return f"r-{provider_id[:20].strip('-')}-"


def status_card_id(provider_id: str) -> str:
    return f"r-{provider_id[:40].strip('-')}-status"[:63]


def valid_link(link: Any) -> str | None:
    """Rule 6: a same-origin path only: starts with /, no scheme, not //, no control characters or backslash."""
    if not isinstance(link, str) or not link.startswith("/") or link.startswith("//") or len(link) > 500:
        return None
    if any(ord(c) < 32 or ord(c) == 127 or c in "\\" for c in link) or "://" in link or ".." in link.split("?")[0].split("/"):
        return None
    return link


def parse_time(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.timestamp()


def _text(value: Any, limit: int) -> str | None:
    return value[:limit] if isinstance(value, str) else None


CHANGED_PATH = "/changed"


@dataclass(frozen=True)
class ChangedPing:
    """A room's out-of-band change signal: the room said something changed."""

    provider_room_id: str | None
    changed: bool
    at: float | None


def parse_changed(doc: Any) -> ChangedPing | None:
    """Parse a room's ``/changed`` ping defensively; None for anything unrecognised.

    Only a JSON object that says ``contract: room/0`` and ``changed: true`` (the literal boolean) is a
    ping. A malformed body, a non-JSON body, a missing/other contract, ``changed: false`` or any other
    value is ignored — never an invalidation, never a raise. An optional ``provider_room_id`` is bounded
    to 200 characters and dropped rather than trusted when it is not a sane string; ``at`` is an optional
    ISO-8601 timestamp. Parsing never fetches: it only decides whether a cache invalidation is warranted.
    """
    if isinstance(doc, (bytes, bytearray)):
        try:
            doc = json.loads(bytes(doc).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
    if not isinstance(doc, dict) or doc.get("contract") != "room/0" or doc.get("changed") is not True:
        return None
    room_id = doc.get("provider_room_id")
    if not isinstance(room_id, str) or not 1 <= len(room_id) <= 200:
        room_id = None
    return ChangedPing(room_id, True, parse_time(doc.get("at")))


@dataclass(frozen=True)
class RoomCard:
    room_id: str
    title: str | None
    body: str | None
    link: str | None
    tone: str
    observed_at: float | None
    stale_after_s: float | None
    malformed: str | None = None


def parse_card(doc: Any) -> RoomCard | None:
    """None when the card cannot even be addressed (no usable id); otherwise a card, possibly flagged malformed."""
    if not isinstance(doc, dict):
        return None
    rid = doc.get("id")
    if not isinstance(rid, str) or not 1 <= len(rid) <= 200:
        return None
    problems = []
    title, body = _text(doc.get("title"), 200), _text(doc.get("body", ""), 2000)
    if not title or not title.strip():
        problems.append("title")
    if body is None:
        problems.append("body")
    tone = doc.get("tone", "update")
    if tone not in TONES:
        log.warning("room card %r has unrecognised tone %r; showing it as 'update'", rid[:40], str(tone)[:30])
        tone = "update"
    link = valid_link(doc.get("link")) if doc.get("link") is not None else None
    fresh = doc.get("freshness")
    observed = parse_time(fresh.get("observed_at")) if isinstance(fresh, dict) else None
    after = fresh.get("stale_after_s") if isinstance(fresh, dict) else None
    if observed is None:
        problems.append("freshness")
    if isinstance(after, bool) or not isinstance(after, (int, float)) or after <= 0:
        after = None
        problems.append("stale_after_s")
    return RoomCard(rid, title if not problems or "title" not in problems else None, body if body is not None else None, link, tone,
                    observed, float(after) if after is not None else None, ",".join(problems) or None)


@dataclass(frozen=True)
class RoomNeed:
    room_id: str
    title: str
    why: str
    link: str | None
    created_at: float | None


def parse_need(doc: Any) -> RoomNeed | None:
    if not isinstance(doc, dict) or not isinstance(doc.get("id"), str) or not 1 <= len(doc["id"]) <= 200:
        return None
    title = _text(doc.get("title"), 200)
    if not title or not title.strip():
        return None
    return RoomNeed(doc["id"], title.strip(), (_text(doc.get("why", ""), 400) or "").strip(),
                    valid_link(doc.get("link")) if doc.get("link") is not None else None, parse_time(doc.get("created_at")))


@dataclass(frozen=True)
class RoomChoice:
    """One offered option for a room action's input: a required value and an optional display label."""

    value: str
    label: str | None = None


@dataclass(frozen=True)
class RoomAction:
    room_id: str
    label: str
    input_schema: dict
    default_autonomy: str
    writes: bool
    choices: tuple[RoomChoice, ...] = ()
    allow_text: bool = False


def parse_choices(value: Any) -> tuple[RoomChoice, ...]:
    """Defensive parse of an action's ``choices``: junk is dropped, duplicates collapse (first wins).

    A choice may be an object with ``value`` (and an optional ``label``) or a bare string. Values are
    trimmed and cut to 120 characters; an empty value is not a choice. At most 20 survive. A malformed
    entry degrades to no choice, never to an exception.
    """
    if not isinstance(value, list):
        return ()
    out: list[RoomChoice] = []
    seen: set[str] = set()
    for item in value:
        if len(out) >= _MAX_CHOICES:
            break
        if isinstance(item, str):
            raw_value, raw_label = item, None
        elif isinstance(item, dict):
            raw_value, raw_label = item.get("value"), item.get("label")
        else:
            continue
        if not isinstance(raw_value, str):
            continue
        choice_value = raw_value.strip()[:_MAX_CHOICE_VALUE].strip()
        if not choice_value or choice_value in seen:
            continue
        label = raw_label.strip()[:_MAX_CHOICE_LABEL].strip() if isinstance(raw_label, str) else ""
        seen.add(choice_value)
        out.append(RoomChoice(choice_value, label or None))
    return tuple(out)


def parse_action(doc: Any) -> RoomAction | None:
    if (not isinstance(doc, dict) or not isinstance(doc.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", doc["id"])
            or ".." in doc["id"] or re.fullmatch(r"[.:-]+", doc["id"])):
        return None
    label = _text(doc.get("label"), 120)
    if not label or not label.strip():
        return None
    schema = doc.get("input_schema") if isinstance(doc.get("input_schema"), dict) else {}
    autonomy = doc.get("default_autonomy")
    return RoomAction(doc["id"], label.strip(), schema, autonomy if autonomy in AUTONOMIES else "ask_first",   # unknown: strictest
                      doc.get("writes") is not False,                                                          # unknown: a write
                      parse_choices(doc.get("choices")),
                      doc.get("allow_text") is True)                                                           # only literal True enables text


# ----------------------------------------------------------------------------- client

@dataclass
class RoomSnapshot:
    provider_id: str
    name: str = ""
    icon: str = "circle"
    status: str = "unknown"
    contract_ok: bool = True
    cards: list[RoomCard] = field(default_factory=list)
    needs: list[RoomNeed] = field(default_factory=list)
    actions: list[RoomAction] = field(default_factory=list)
    error_class: str | None = None
    note: str = ""
    status_code: int | None = None
    duration_ms: int | None = None
    fetched_at: float = 0.0
    last_good_at: float | None = None
    stale: bool = False


class Room0Client:
    """Reads a room through the confinement seam, with a short cache, failure back-off and last-good fallback.

    Home must stay fast on a bad day: a failing room is not retried for 30 s (doubling to 5 min), a request
    never waits long behind another request's in-flight fetch, and a room always answers with SOMETHING
    (its last-known cards stale, or an explicit unavailable status), never silence.
    """

    FAIL_BACKOFF_S = 30.0
    FAIL_BACKOFF_MAX_S = 300.0
    LOCK_WAIT_S = 0.25

    def __init__(self, store: Any, send: Callable[..., Any] = confined_request, *, clock: Callable[[], float] = time.time,
                 ttl_s: float = 15.0):
        self._store, self._send, self._clock, self._ttl = store, send, clock, ttl_s
        self._cache: dict[str, RoomSnapshot] = {}
        self._good: dict[str, RoomSnapshot] = {}
        self._fails: dict[str, tuple[int, float]] = {}    # provider -> (consecutive failures, next attempt at)
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def provider(self, provider_id: str) -> Provider | None:
        p = self._store.get("provider", provider_id)
        return p if p is not None and p.kind == "room0" else None

    def snapshot(self, provider_id: str, *, force: bool = False) -> RoomSnapshot | None:
        provider = self.provider(provider_id)
        if provider is None:
            return None
        now = self._clock()
        cached = self._cache.get(provider_id)
        if not force and cached is not None:
            if cached.error_class is None and now - cached.fetched_at < self._ttl:
                return cached
            if cached.error_class is not None and now < self._fails.get(provider_id, (0, 0.0))[1]:
                return cached                                  # a failing room is left alone until its back-off ends
        with self._guard:
            lock = self._locks.setdefault(provider_id, threading.Lock())
        if not lock.acquire(timeout=self.LOCK_WAIT_S):         # someone is already fetching: do not queue behind them
            return self._cache.get(provider_id) or self._unavailable(provider, "still being fetched")
        try:
            snap = self._fetch(provider)
            self._cache[provider_id] = snap
            if snap.error_class is None:
                self._good[provider_id] = snap
                self._fails.pop(provider_id, None)
            else:
                count = self._fails.get(provider_id, (0, 0.0))[0] + 1
                delay = min(self.FAIL_BACKOFF_S * 2 ** min(count - 1, 8), self.FAIL_BACKOFF_MAX_S)
                self._fails[provider_id] = (count, self._clock() + delay)
            return snap
        finally:
            lock.release()

    def invalidate(self, provider_id: str) -> bool:
        """Owner/room said this room changed: drop its cached snapshot so the next read refetches.

        Removes the cached snapshot, the last-good fallback and the failure back-off, and sends NOTHING
        to the room: invalidation never fetches and never fabricates data. Returns ``False`` when the id
        is not a room0 provider (nothing to invalidate). The last-good mechanism itself is unchanged: the
        next successful read repopulates it, so a later fetch failure can still show those last-known
        cards stale.
        """
        if self.provider(provider_id) is None:
            return False
        with self._guard:
            self._cache.pop(provider_id, None)
            self._good.pop(provider_id, None)
            self._fails.pop(provider_id, None)
        return True

    def _unavailable(self, provider: Provider, note: str) -> RoomSnapshot:
        """An explicit unavailable answer (never a missing room): last-known content, stale, if there is any."""
        snap = RoomSnapshot(provider.id, name=provider.name, fetched_at=self._clock())
        return self._failed(snap, ConfinementError("timeout", note))

    # ---- internals

    def _get(self, provider: Provider, path: str) -> tuple[Any, ConfinementError | None, RawResponse | None]:
        request = Request(id=f"{provider.id}.room", provider=provider.id, path=path, ttl_s=0)
        try:
            result = send_scoped(self._send, provider, request, effect="read")
        except Exception:
            return None, ConfinementError("connection", "sender error"), None
        if isinstance(result, ConfinementError):
            return None, result, None
        code = result.status_code
        if code in (401, 403):
            return None, ConfinementError("auth_failed", f"room answered {code}", status_code=code, duration_ms=result.duration_ms), result
        if 400 <= code < 500:
            return None, ConfinementError("http_4xx", f"room answered {code}", status_code=code, duration_ms=result.duration_ms), result
        if code >= 500 or code < 200 or code >= 300:
            return None, ConfinementError("http_5xx", f"room answered {code}", status_code=code, duration_ms=result.duration_ms), result
        try:
            return json.loads(result.body.decode("utf-8")), None, result
        except (ValueError, UnicodeDecodeError):
            return None, ConfinementError("malformed", "room sent something that is not JSON", status_code=code,
                                          duration_ms=result.duration_ms), result

    def _fetch(self, provider: Provider) -> RoomSnapshot:
        now = self._clock()
        snap = RoomSnapshot(provider.id, name=provider.name, fetched_at=now)
        doc, err, resp = self._get(provider, "/room")
        if err is not None:
            return self._failed(snap, err)
        snap.duration_ms = resp.duration_ms if resp else None
        snap.status_code = resp.status_code if resp else None
        if not isinstance(doc, dict) or doc.get("contract") != "room/0":
            snap.contract_ok = False
            return self._failed(snap, ConfinementError("malformed", "room does not speak room/0"))
        name = _text(doc.get("name"), 80)
        snap.name = name.strip() if name and name.strip() else provider.name
        snap.icon = doc["icon"] if isinstance(doc.get("icon"), str) and _ICON.match(doc["icon"]) else "circle"
        snap.status = doc.get("status") if doc.get("status") in STATE_FOR_STATUS else "unknown"
        for path, key, parser, cap in (("/room/cards", "cards", parse_card, _MAX_CARDS), ("/room/needs-you", "needs", parse_need, _MAX_NEEDS),
                                       ("/room/actions", "actions", parse_action, _MAX_ACTIONS)):
            data, err, _ = self._get(provider, path)
            if err is not None:
                return self._failed(snap, err)
            if not isinstance(data, list):
                return self._failed(snap, ConfinementError("malformed", f"{path} is not a list"))
            setattr(snap, key, [x for x in (parser(d) for d in data[:cap]) if x is not None])
        snap.last_good_at = now
        return snap

    def _failed(self, snap: RoomSnapshot, err: ConfinementError) -> RoomSnapshot:
        snap.error_class, snap.note, snap.stale = err.error_class, (err.note or "")[:200], True
        snap.status_code = err.status_code
        snap.duration_ms = err.duration_ms
        good = self._good.get(snap.provider_id)
        if good is not None:  # last-known content, shown stale, never as current
            snap.name, snap.icon, snap.cards, snap.needs, snap.actions = good.name, good.icon, good.cards, good.needs, good.actions
            snap.last_good_at = good.last_good_at
        return snap


# --------------------------------------------------------------------------- mapping

def card_envelope(provider: Provider, snap: RoomSnapshot, card: RoomCard | None, *, now: float) -> dict[str, Any]:
    """The C2 envelope for one room card (or, with card None, for the room's own status card)."""
    def iso(t: float | None) -> str | None:
        return None if t is None else dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    stale = snap.stale
    state = STATE_FOR_ERROR.get(snap.error_class or "", "unknown") if snap.error_class else STATE_FOR_STATUS.get(snap.status, "unknown")
    if not snap.contract_ok:
        state = "degraded"
    values: dict[str, dict[str, Any]]
    if card is None:
        values = {"status": {"text": snap.status if not snap.error_class else "unreachable"}}
        title = snap.name or provider.name
    elif card.malformed and (card.title is None or card.body is None):
        values, state, title = {"body": {"text": "unknown"}}, "degraded", (card.title or snap.name or provider.name)
    else:
        title = card.title or ""
        values = {"body": {"text": card.body or ""}}
        if card.observed_at is not None and card.stale_after_s is not None and now > card.observed_at + card.stale_after_s:
            stale = True                       # rule 3: past stale_after_s it is stale, never current
        if card.malformed:
            state = "degraded"
        if card.link and provider.public_url:
            values["link"] = {"text": card.link, "raw": provider.public_url.rstrip("/") + card.link}
    evidence = {"request_id": f"{provider.id}.room", "method": "GET", "path": "/room/cards" if card else "/room",
                "status_code": snap.status_code, "duration_ms": snap.duration_ms, "error_class": snap.error_class}
    if snap.note:
        evidence["note"] = snap.note
    return {"card_id": room_card_id(provider.id, card.room_id) if card else status_card_id(provider.id),
            "source_state": state, "freshness": "stale" if stale else "current", "observed_at": iso(now),
            "fetched_at": iso(snap.fetched_at), "last_good_at": iso(snap.last_good_at),
            "values": values, "meter": None,
            "meaning": {"short": title, "full": f"Reported by the {snap.name or provider.name} room."}, "evidence": evidence}


def card_defs(provider: Provider, snap: RoomSnapshot, card: RoomCard | None) -> dict[str, Any]:
    """The C6 display definition for a room card (display only)."""
    has_link = bool(card and card.link and provider.public_url)
    title = (card.title if card and card.title else (snap.name or provider.name))
    return {"card": room_card_id(provider.id, card.room_id) if card else status_card_id(provider.id), "size": "M", "hidden": False,
            "title": title, "icon": snap.icon, "group": provider.group, "view": "link" if has_link else "stat",
            "fields": [{"key": "link" if has_link else ("body" if card else "status"), "label": title, "format": "text", "unit": None}],
            "meter_type": None}


# ---------------------------------------------------------------------------- service

class RoomService:
    def __init__(self, store: Any, client: Room0Client, *, clock: Callable[[], float] = time.time):
        self._store, self._client, self._clock = store, client, clock
        self._pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="worlds-rooms")

    def providers(self) -> list[Provider]:
        return sorted((o for k, o in self._store.iter_all() if k == "provider" and o.kind == "room0"), key=lambda p: p.id)

    SNAPSHOT_BUDGET_S = 2.0

    def _snapshots(self, only: list[Provider] | None = None) -> list[tuple[Provider, RoomSnapshot]]:
        """One snapshot per room, always: a room that has not answered within the budget is shown as
        unavailable (its fetch carries on in the background and fills the cache), never dropped."""
        providers = only if only is not None else self.providers()
        futures = [(p, self._pool.submit(self._client.snapshot, p.id)) for p in providers]
        done, _ = wait([f for _, f in futures], timeout=self.SNAPSHOT_BUDGET_S)
        out = []
        for p, f in futures:
            snap = None
            if f in done:
                try:
                    snap = f.result()
                except Exception:
                    snap = None
            if snap is None:
                cached = self._client._cache.get(p.id)
                # past its TTL this is not current: serve it marked stale, never as fresh
                snap = replace(cached, stale=True) if cached is not None else self._client._unavailable(p, "no answer in time")
            out.append((p, snap))
        return out

    def home_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for provider, snap in self._snapshots():
            if snap.cards:
                items.extend(card_defs(provider, snap, c) for c in snap.cards)
            elif snap.error_class or not snap.contract_ok:
                items.append(card_defs(provider, snap, None))      # an unreachable room is shown as such (rule 12)
        return items

    def card(self, card_id: str) -> dict[str, Any] | None:
        """The envelope for one room card: only the room(s) whose id prefix matches are asked."""
        if not isinstance(card_id, str) or not card_id.startswith("r-"):
            return None
        now = self._clock()
        mine = [p for p in self.providers() if card_id == status_card_id(p.id) or card_id.startswith(card_prefix(p.id))]
        for provider, snap in self._snapshots(mine):
            if card_id == status_card_id(provider.id) and (snap.error_class or not snap.cards):
                return card_envelope(provider, snap, None, now=now)
            for c in snap.cards:
                if room_card_id(provider.id, c.room_id) == card_id:
                    return card_envelope(provider, snap, c, now=now)
        return None

    def needs(self) -> list[dict[str, Any]]:
        out = []
        for provider, snap in self._snapshots():
            for n in snap.needs:
                href = (provider.public_url.rstrip("/") + n.link) if n.link and provider.public_url else None
                action: dict[str, Any] = {"kind": "open"}
                if href:
                    action["href"] = href
                out.append({"id": f"room:{provider.id}:{slug(n.room_id, 40)}", "text": (f"{n.title} — {n.why}" if n.why else n.title)[:300],
                            "source": snap.name or provider.name, "created_at": n.created_at or snap.fetched_at, "action": action})
        return out

    def rooms(self) -> list[dict[str, Any]]:
        return [{"id": p.id, "name": snap.name or p.name, "status": snap.status, "reachable": snap.error_class is None,
                 "error_class": snap.error_class, "last_seen_at": snap.last_good_at, "contract_ok": snap.contract_ok,
                 "governance": "project_home" if p.governed_by_project_home() else "worlds"} for p, snap in self._snapshots()]

    def invalidate(self, provider_id: str) -> bool:
        """A room signalled a change (its ``/changed`` ping): drop its snapshot; sends nothing to the room."""
        return self._client.invalidate(provider_id)

    # ---- action candidates (C1 actions the owner may adopt)

    @staticmethod
    def _ids(provider_id: str, room_action_id: str) -> tuple[str, str]:
        s = slug(room_action_id, 30)
        h = hashlib.sha256(room_action_id.encode()).hexdigest()[:6]     # a.b / a:b / a-b must not collide
        return f"{provider_id}.act-{s}-{h}"[:127], f"{provider_id[:20].strip('-')}-{s}-{h}"[:63].rstrip("-")

    @staticmethod
    def _check_room_action_id(room_action_id: str) -> None:
        if (not isinstance(room_action_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", room_action_id)
                or ".." in room_action_id or re.fullmatch(r"[.:-]+", room_action_id)):
            raise ValueError("that is not a valid room action id")

    def candidates(self, provider_id: str) -> list[dict[str, Any]] | None:
        snap = self._client.snapshot(provider_id)
        if snap is None:
            return None
        out = []
        for a in snap.actions:
            _, action_id = self._ids(provider_id, a.room_id)
            stored = self._store.get("action", action_id)
            out.append({"room_action_id": a.room_id, "label": a.label, "writes": a.writes, "default_autonomy": a.default_autonomy,
                        "adopted": isinstance(stored, Action) and stored.state == "adopted", "action_id": action_id,
                        "choices": [{"value": c.value, "label": c.label} for c in a.choices], "allow_text": a.allow_text})
        return out

    def adopted(self, provider_id: str, room_action_id: str) -> Action | None:
        """The already-adopted C1 action for a room action, or None. Never adopts, never sends a write.

        The room must still offer it: an adopted action the room no longer lists has nothing honest to
        answer, so it is refused too. Raises ValueError for an id no room action could have.
        """
        self._check_room_action_id(room_action_id)
        if self._client.provider(provider_id) is None:
            return None
        snap = self._client.snapshot(provider_id)
        if snap is None or snap.error_class is not None or not any(a.room_id == room_action_id for a in snap.actions):
            return None
        _, action_id = self._ids(provider_id, room_action_id)
        action = self._store.get("action", action_id)
        return action if isinstance(action, Action) else None

    def answer(self, provider_id: str, room_action_id: str, params: dict[str, Any] | None, principal: Any,
               dispatcher: Any, *, idempotency_key: str | None = None,
               project_home_approval_id: str | None = None) -> dict[str, Any] | None:
        """Answer a room need by running an ALREADY-ADOPTED room action through the C3 dispatcher.

        This does not shortcut the authority: ``request_authorization -> approve -> consume -> dispatch``
        is the same lifecycle every write takes, so nothing is sent without a consumed authorization and
        there is at most one network attempt. The adopted request carries no body, so the answer payload
        (``params``) becomes the body through the dispatcher's existing mechanism. A Project Home-governed
        room is approved there and only recorded here (``project_home_approval_id``); without it the
        dispatcher refuses. Returns the receipt, or None when the action is not callable.
        """
        action = self.adopted(provider_id, room_action_id)
        if action is None:
            return None
        if not idempotency_key:
            idempotency_key = uuid.uuid4().hex                 # a room action always requires one (C8)
        authorization = dispatcher.request_authorization(principal, action.id, params, idempotency_key)
        provider = self._client.provider(provider_id)
        if provider is not None and provider.governed_by_project_home() and project_home_approval_id:
            dispatcher.record_project_home_approval(authorization["id"], project_home_approval_id)
        else:
            dispatcher.approve(principal, authorization["id"])
        return dispatcher.execute(principal, authorization["id"])

    def adopt(self, provider_id: str, room_action_id: str) -> Action | None:
        """Owner adoption: a callable C1 action (never exposed, always approval, treated as a write,
        idempotency key required). Nothing is sent. Returns None when the room has no such action; raises
        ValueError (a plain message) for an id no room action could have."""
        self._check_room_action_id(room_action_id)
        provider = self._client.provider(provider_id)
        snap = self._client.snapshot(provider_id)
        if provider is None or snap is None:
            return None
        found = next((a for a in snap.actions if a.room_id == room_action_id), None)
        if found is None:
            return None
        request_id, action_id = self._ids(provider_id, found.room_id)
        if self._store.get("action", action_id) is not None:
            return self._store.get("action", action_id)
        wanted_path = f"/room/actions/{quote(found.room_id, safe='')}"
        leftover = self._store.get("request", request_id)
        if leftover is None:
            self._store.save("request", Request(id=request_id, provider=provider_id, method="POST", path=wanted_path, ttl_s=0), etag="")
        elif not (leftover.provider == provider_id and leftover.method == "POST" and leftover.path == wanted_path
                  and leftover.body is None and leftover.resolved_effect() == "write"):
            # only a request that is exactly this room action's own is reused; anything else is not ours to reuse
            raise ConfigInvalid(f"request {request_id} already exists and is not this room action's request")
        action = Action(id=action_id, request=request_id, name=found.label, access="write", approval="always",
                        scope=f"room.{provider_id}.{slug(found.room_id, 40)}", idempotency="required", exposed=False)
        self._store.save("action", action, etag="")
        return action
