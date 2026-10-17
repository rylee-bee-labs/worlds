"""Web Push: the standards-based transport of the notifications capability.

Conceptually this is one more way a notification reaches a person —
alongside the webhook and ntfy adapters in
``providers/native_notifications.py`` — built on the browser's own push
services (Apple, Google, Mozilla). No third-party notification server:
Worlds signs each delivery with a VAPID key and hands the payload to
the push service the browser already trusts.

What lives where (all per person, through ``identity.principal_scoped_path``):

* ``push_subscriptions`` — the devices a person turned push on for.
  Each record holds the endpoint and the browser's encryption keys;
  they are credentials and leave the store only toward the push
  service, never in an API response.
* ``notifications`` — the person's notification history (every
  notification is stored before anything is pushed) plus their
  delivery preferences (tiers, sources, quiet hours).

The VAPID private key is read from the environment
(``PW_VAPID_PRIVATE_KEY``, a PEM block or a base64url raw/DER key —
see docs/NOTIFICATIONS.md) and the contact for ``PW_VAPID_SUBJECT``.
Neither is ever logged, stored on disk by this app, or echoed in a
response. With no key set, push is ``not_configured`` and everything
else (history, preferences, the rest of the world) keeps working.

Time is injectable (``hub.now()``) so the quiet-hours and rate-limit
behavior can be tested against a fake clock.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.parse
import uuid
from collections import deque
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # the old app's identity layer; imported lazily so the front door never loads it
    from .identity import Principal

_logger = logging.getLogger("personal_world.push")

#: The one outbound call. Module level so tests replace it (no network).
try:  # pragma: no cover - import shape, not logic
    from pywebpush import WebPushException
    from pywebpush import webpush as _webpush
except ImportError:  # pragma: no cover - pywebpush is a declared dependency
    _webpush = None  # type: ignore[assignment]

    class WebPushException(Exception):  # type: ignore[no-redef]
        @property
        def status_code(self) -> int | None:
            return None


#: VAPID material comes from the environment only (see docs/NOTIFICATIONS.md).
PRIVATE_KEY_ENV = "PW_VAPID_PRIVATE_KEY"
SUBJECT_ENV = "PW_VAPID_SUBJECT"

#: A push the phone is asleep for lives at most a day.
TTL_SECONDS = 24 * 60 * 60

#: The three tiers, and the words a device shows in front of each.
#: Only GOOD NEWS pushes by default; "A small update" and "When you're
#: ready" go to history until the person turns them on (design boards,
#: owner-approved 2026-09-26: "quiet by default").
TIER_WORDS: dict[str, str] = {
    "good_news": "GOOD NEWS",
    "update": "A SMALL UPDATE",
    "when_ready": "WHEN YOU'RE READY",
}
TIERS: tuple[str, ...] = ("good_news", "update", "when_ready")

#: History is kept this long (design: 90 days).
HISTORY_DAYS = 90

#: How a source is named on the notification (the sender).
SOURCE_NAMES: dict[str, str] = {
    "vefr": "VEFR", "candy": "Candy", "agent": "An agent", "cli": "A tool",
    "api": "Worlds", "worlds": "Worlds",
}


def sender_name(source: str | None) -> str:
    s = (source or "").strip()
    return SOURCE_NAMES.get(s.lower(), s.replace("-", " ").title() or "Worlds")


#: Publishing may not run away with a person's phone.
RATE_LIMIT_PER_MINUTE = 30

#: A dedupe key collapses repeats for this long.
DEDUPE_WINDOW_SECONDS = 24 * 60 * 60

#: Device labels come from the browser; keep them short and plain.
_MAX_LABEL_LEN = 80

_HHMM = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")

DEFAULT_PREFS: dict[str, Any] = {
    "tiers": {"good_news": True, "update": False, "when_ready": False},
    "sources": {},
    "quiet_hours": {"on": True, "start": "21:00", "end": "08:00", "tz": None},
}


class PrefsError(ValueError):
    """A preference body the server will not accept. Message is plain
    words and safe to show."""


def _now_epoch() -> float:
    return time.time()


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def valid_same_origin_link(link: Any) -> str | None:
    """A notification link must be a same-origin path (like room links).

    ``None``/empty means no link. Anything with a scheme, a host, a
    protocol-relative start or a backslash is refused (``ValueError``):
    a notification must never point a phone at someone else's site.
    """
    if link is None or link == "":
        return None
    if not isinstance(link, str) or "\r" in link or "\n" in link:
        raise ValueError("link must be a path on this site")
    try:
        parts = urllib.parse.urlsplit(link)
    except ValueError:
        raise ValueError("link must be a path on this site") from None
    if parts.scheme or parts.netloc or "\\" in link or not link.startswith("/"):
        raise ValueError("link must be a path on this site")
    return link


# ── VAPID keys ──────────────────────────────────────────────────────


def generate_keypair() -> dict[str, str]:
    """A fresh VAPID key pair, for the operator (`push keygen`).

    The private key is printed as a PEM block (the form that rides most
    easily in an env file); the public key is base64url, the form
    browsers subscribe with. This function only returns strings — the
    app never writes either to disk.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    pub = key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return {
        "private_pem": pem,
        "public_key": base64.urlsafe_b64encode(pub).decode("ascii").rstrip("="),
    }


def load_vapid(private_value: str):
    """Environment value → a py_vapid object (PEM text or base64url key).

    Raises ``ValueError`` for unreadable input; the raw value is never
    included in the error or any log line.
    """
    from py_vapid import Vapid

    value = (private_value or "").strip()
    if not value:
        raise ValueError("empty private key")
    try:
        if "-----BEGIN" in value:
            return Vapid.from_pem(value.encode("utf-8"))
        return Vapid.from_string(value)
    except Exception as exc:
        raise ValueError(f"unreadable VAPID private key ({type(exc).__name__})") from None


def public_key_for(private_value: str) -> str:
    """Derive the base64url public key from the private key."""
    from cryptography.hazmat.primitives import serialization

    vapid = load_vapid(private_value)
    pub = vapid.private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(pub).decode("ascii").rstrip("=")


def subject_ok(subject: str) -> bool:
    """VAPID wants a contact URI: mailto:… or https:… — nothing else."""
    return subject.startswith(("mailto:", "https:"))


# ── quiet hours ─────────────────────────────────────────────────────


def _minutes_of(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _wall_datetime(epoch: float, tz_name: str | None) -> datetime:
    """The person's wall clock: their zone when the prefs name one, the
    machine's own clock otherwise."""
    if tz_name:
        try:
            from zoneinfo import ZoneInfo

            return datetime.fromtimestamp(epoch, ZoneInfo(tz_name))
        except (KeyError, ValueError, OSError):
            pass
    return datetime.fromtimestamp(epoch).astimezone()


def in_quiet_hours(prefs: dict, epoch: float) -> bool:
    """True when ``epoch`` falls inside the person's quiet window.

    The window may wrap midnight (21:00→08:00); start == end is not
    quiet all day but never quiet (a zero-length window: off by intent,
    since ``on`` already carries the switch).
    """
    quiet = prefs.get("quiet_hours") or {}
    if not quiet.get("on"):
        return False
    start = quiet.get("start") or DEFAULT_PREFS["quiet_hours"]["start"]
    end = quiet.get("end") or DEFAULT_PREFS["quiet_hours"]["end"]
    if not (_HHMM.match(str(start)) and _HHMM.match(str(end))):
        return False
    now = _wall_datetime(epoch, quiet.get("tz"))
    minutes = now.hour * 60 + now.minute
    s, e = _minutes_of(str(start)), _minutes_of(str(end))
    if s == e:
        return False
    if s < e:
        return s <= minutes < e
    return minutes >= s or minutes < e


# ── per-person stores ───────────────────────────────────────────────


class _JsonStore:
    """One JSON file, read-modify-write under a lock, atomically saved.

    Corrupt or unreadable files are treated as empty (fail toward no
    state) and the event is logged once, visibly — like the scheduler's
    own loader, but without a journal to fall back on.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as exc:
            _logger.warning(
                "notifications state %s unreadable (%s: %s) — starting empty; "
                "the next save will replace the file",
                self.path.name,
                type(exc).__name__,
                exc,
            )
            return {}

    def _save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def mutate(self, fn: Callable[[dict], Any]) -> Any:
        with self._lock:
            data = self._load()
            result = fn(data)
            self._save(data)
            return result


class SubscriptionStore(_JsonStore):
    """The push devices a person turned on, per person.

    Upsert is by endpoint: a browser that re-subscribes (keys rotate
    over time) updates its record instead of stacking duplicates.
    """

    def upsert(self, subscription: dict, device_label: str, now: float) -> tuple[str, bool]:
        endpoint = (subscription or {}).get("endpoint")
        keys = (subscription or {}).get("keys") or {}
        if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            raise ValueError("subscription endpoint must be an https address")
        if not isinstance(keys, dict) or not keys.get("p256dh") or not keys.get("auth"):
            raise ValueError("subscription is missing its browser keys")
        label = str(device_label or "").strip()[:_MAX_LABEL_LEN]
        sub_id = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:16]

        def _do(data: dict) -> tuple[str, bool]:
            subs = data.setdefault("subscriptions", [])
            for rec in subs:
                if rec.get("endpoint") == endpoint:
                    rec["keys"] = {"p256dh": str(keys["p256dh"]), "auth": str(keys["auth"])}
                    rec["device_label"] = label or rec.get("device_label", "")
                    rec["last_ok_at"] = None
                    rec["last_error"] = None
                    return sub_id, False
            subs.append(
                {
                    "id": sub_id,
                    "endpoint": endpoint,
                    "keys": {"p256dh": str(keys["p256dh"]), "auth": str(keys["auth"])},
                    "device_label": label,
                    "created_at": now,
                    "last_ok_at": None,
                    "last_error": None,
                }
            )
            return sub_id, True

        return self.mutate(_do)

    def public_rows(self, now: float) -> list[dict]:
        """What a person may list about their own devices: labels and
        times, never endpoints or keys."""
        rows = []
        for rec in self._load().get("subscriptions", []):
            rows.append(
                {
                    "id": rec.get("id"),
                    "device_label": rec.get("device_label") or "this device",
                    "created_at": _iso(rec.get("created_at")),
                    "last_ok_at": _iso(rec.get("last_ok_at") or None),
                    "last_error": rec.get("last_error"),
                }
            )
        return rows

    def remove(self, sub_id: str) -> bool:
        def _do(data: dict) -> bool:
            subs = data.get("subscriptions", [])
            kept = [r for r in subs if r.get("id") != sub_id]
            data["subscriptions"] = kept
            return len(kept) != len(subs)

        return self.mutate(_do)

    def for_send(self) -> list[dict]:
        return [dict(r) for r in self._load().get("subscriptions", [])]

    def mark_ok(self, sub_id: str, now: float) -> None:
        def _do(data: dict) -> None:
            for rec in data.get("subscriptions", []):
                if rec.get("id") == sub_id:
                    rec["last_ok_at"] = now
                    rec["last_error"] = None

        self.mutate(_do)

    def mark_error(self, sub_id: str, words: str) -> None:
        """Record WHY a device stopped answering, in plain words only.

        The caller sanitizes: never an exception message that could
        carry the endpoint URL or key material.
        """

        def _do(data: dict) -> None:
            for rec in data.get("subscriptions", []):
                if rec.get("id") == sub_id:
                    rec["last_error"] = words[:120]

        self.mutate(_do)


class NotificationStore(_JsonStore):
    """One person's notification history and delivery preferences.

    Every notification is stored here BEFORE any push leaves the
    process; the push outcome only updates the record's state.
    """

    def prefs(self) -> dict:
        return _merge_prefs(json.loads(json.dumps(DEFAULT_PREFS)), self._load().get("prefs") or {})

    def set_prefs(self, prefs: dict) -> dict:
        clean = _validate_prefs(prefs)

        def _do(data: dict) -> dict:
            data["prefs"] = clean
            return json.loads(json.dumps(clean))

        return self.mutate(_do)

    def add(self, record: dict) -> None:
        def _do(data: dict) -> None:
            items = data.setdefault("items", [])
            items.append(record)
            # history is bounded: 90 days, and at most the newest 500
            cutoff = float(record.get("created_at") or _now_epoch()) - HISTORY_DAYS * 86400
            items[:] = [i for i in items if float(i.get("created_at") or 0) >= cutoff]
            if len(items) > 500:
                del items[: len(items) - 500]

        self.mutate(_do)

    def update_state(self, note_id: str, **changes: Any) -> None:
        def _do(data: dict) -> None:
            for rec in data.get("items", []):
                if rec.get("id") == note_id:
                    rec.update(changes)

        self.mutate(_do)

    def list(self, unread: bool, limit: int, now: float) -> list[dict]:
        items = self._load().get("items", [])
        if unread:
            items = [r for r in items if not r.get("read_at")]
        newest_first = sorted(items, key=lambda r: r.get("created_at") or 0, reverse=True)
        return [
            {
                "id": r.get("id"),
                "tier": r.get("tier"),
                "tier_words": TIER_WORDS.get(r.get("tier", ""), ""),
                "source": r.get("source"),
                "title": r.get("title"),
                "body": r.get("body"),
                "link": r.get("link"),
                "created_at": _iso(r.get("created_at")),
                "read_at": _iso(r.get("read_at")),
                "state": r.get("state"),
            }
            for r in newest_first[:limit]
        ]

    def get(self, note_id: str) -> dict | None:
        for rec in self._load().get("items", []):
            if rec.get("id") == note_id:
                return rec
        return None

    def mark_read(self, note_id: str, now: float) -> bool:
        def _do(data: dict) -> bool:
            for rec in data.get("items", []):
                if rec.get("id") == note_id and not rec.get("read_at"):
                    rec["read_at"] = now
                    return True
            return False

        return self.mutate(_do)

    def read_all(self, now: float) -> int:
        count = 0

        def _do(data: dict) -> int:
            nonlocal count
            for rec in data.get("items", []):
                if not rec.get("read_at"):
                    rec["read_at"] = now
                    count += 1
            return count

        return self.mutate(_do)

    def deferred(self) -> list[dict]:
        return [
            dict(r)
            for r in self._load().get("items", [])
            if r.get("state") == "deferred"
        ]

    def dedupe_hit(self, key: str, now: float) -> str | None:
        """The id of a notification stored with this dedupe key inside
        the 24-hour window, or None."""

        def _do(data: dict) -> str | None:
            entries = data.get("dedupe") or {}
            entry = entries.get(key)
            if isinstance(entry, dict) and now - float(entry.get("at") or 0) < DEDUPE_WINDOW_SECONDS:
                hit = entry.get("id")
                return str(hit) if hit else None
            return None

        return self.mutate(_do)

    def dedupe_note(self, key: str, note_id: str, now: float) -> None:
        def _do(data: dict) -> None:
            entries = data.setdefault("dedupe", {})
            entries[key] = {"id": note_id, "at": now}
            for stale in [
                k
                for k, v in entries.items()
                if isinstance(v, dict) and now - float(v.get("at") or 0) >= DEDUPE_WINDOW_SECONDS
            ]:
                del entries[stale]

        self.mutate(_do)


def _merge_prefs(base: dict, over: dict) -> dict:
    """A stored prefs dict over the defaults, key by key (a partial
    store from before a new default was added still reads complete)."""
    for section in ("tiers", "sources", "quiet_hours"):
        value = over.get(section)
        if isinstance(value, dict):
            base[section].update(value)
    return base


def _validate_prefs(body: dict) -> dict:
    """The closed shape of notification prefs; anything else raises
    ``PrefsError`` with a plain message."""
    if not isinstance(body, dict):
        raise PrefsError("preferences must be an object")
    out = json.loads(json.dumps(DEFAULT_PREFS))
    tiers = body.get("tiers")
    if tiers is not None:
        if not isinstance(tiers, dict):
            raise PrefsError("tiers must be an object of on/off values")
        for key, value in tiers.items():
            if key not in TIERS or not isinstance(value, bool):
                raise PrefsError("tiers are good_news, update and when_ready, each on/off")
            out["tiers"][key] = value
    sources = body.get("sources")
    if sources is not None:
        if not isinstance(sources, dict):
            raise PrefsError("sources must be an object of on/off values")
        for key, value in sources.items():
            if not isinstance(key, str) or not key or len(key) > 40 or not isinstance(value, bool):
                raise PrefsError("a source is a short name with an on/off value")
            out["sources"][key] = value
    quiet = body.get("quiet_hours")
    if quiet is not None:
        if not isinstance(quiet, dict):
            raise PrefsError("quiet hours must be an object")
        for key in quiet:
            if key not in ("on", "start", "end", "tz"):
                raise PrefsError("quiet hours are on, start, end and tz")
        if "on" in quiet and not isinstance(quiet["on"], bool):
            raise PrefsError("quiet hours on/off must be true or false")
        for key in ("start", "end"):
            if key in quiet:
                value = quiet[key]
                if not isinstance(value, str) or not _HHMM.match(value):
                    raise PrefsError(f"quiet hours {key} must look like 21:00")
                out["quiet_hours"][key] = value
        if "tz" in quiet:
            tz = quiet["tz"]
            if tz is not None:
                if not isinstance(tz, str) or not tz or len(tz) > 64:
                    raise PrefsError("quiet hours tz must be a time zone name or null")
                try:
                    from zoneinfo import ZoneInfo

                    ZoneInfo(tz)
                except (KeyError, ValueError, OSError):
                    raise PrefsError("quiet hours tz is not a time zone I know") from None
            out["quiet_hours"]["tz"] = tz
        out["quiet_hours"].update({k: v for k, v in quiet.items() if k in ("on",)})
    return out


# ── the hub: everything the API routes call ─────────────────────────


class PushHub:
    """One hub per app. Resolves per-person stores, checks the VAPID
    environment, and pushes. Never crashes a request: a failed delivery
    is recorded on the device or the notification, visibly."""

    def __init__(self, data_dir: Path, mode: str = "single",
                 store_path: Callable[[str, str], Path] | None = None) -> None:
        """``store_path(person_id, kind)`` names a store's file. Without it the old app's
        ``identity.principal_scoped_path`` is used (imported only then), so the front door,
        which passes its own, never loads the old identity layer."""
        self.data_dir = Path(data_dir)
        self.mode = mode
        self._store_path = store_path
        self.now: Callable[[], float] = _now_epoch
        #: who to deliver to when a background tick has no principal
        self.person_ids: Callable[[], list[str]] = self._default_person_ids
        self._rate: dict[str, deque[float]] = {}
        self._rate_lock = threading.Lock()
        self._vapid_cache: tuple[str, Any] | None = None

    # -- keys / status ---------------------------------------------------

    def private_value(self) -> str:
        return os.environ.get(PRIVATE_KEY_ENV, "").strip()

    def subject(self) -> str:
        return os.environ.get(SUBJECT_ENV, "").strip()

    def configured(self) -> bool:
        """True only with a private key AND a usable subject: half a
        VAPID setup cannot sign anything, and saying so is honest."""
        return bool(self.private_value()) and subject_ok(self.subject())

    def public_key(self) -> str | None:
        value = self.private_value()
        if not value:
            return None
        try:
            return public_key_for(value)
        except ValueError:
            return None

    def _vapid(self):
        value = self.private_value()
        if not value:
            return None
        cached = self._vapid_cache
        if cached is not None and cached[0] == value:
            return cached[1]
        try:
            vapid = load_vapid(value)
        except ValueError as exc:
            _logger.warning("push: %s — push is off until the key reads", exc)
            return None
        self._vapid_cache = (value, vapid)
        return vapid

    # -- per-person stores -------------------------------------------------

    def _default_person_ids(self) -> list[str]:
        if self._store_path is not None:
            return ["owner"]
        from .identity import BOOTSTRAP_PRINCIPAL_ID
        return [BOOTSTRAP_PRINCIPAL_ID]

    def _person(self, person_id: str) -> Principal:
        from .identity import Principal
        return Principal(id=person_id, kind="person", source="push")

    def _path(self, person_id: str, kind: str) -> Path:
        if self._store_path is not None:
            return self._store_path(person_id, kind)
        from .identity import principal_scoped_path
        return principal_scoped_path(self.data_dir, self._person(person_id), kind, mode=self.mode)

    def _sub_store(self, person_id: str) -> SubscriptionStore:
        return SubscriptionStore(self._path(person_id, "push_subscriptions"))

    def _note_store(self, person_id: str) -> NotificationStore:
        return NotificationStore(self._path(person_id, "notifications"))

    # -- subscriptions -------------------------------------------------------

    def add_subscription(self, person_id: str, subscription: dict, device_label: str) -> tuple[str, bool]:
        return self._sub_store(person_id).upsert(subscription or {}, device_label, self.now())

    def list_subscriptions(self, person_id: str) -> list[dict]:
        return self._sub_store(person_id).public_rows(self.now())

    def remove_subscription(self, person_id: str, sub_id: str) -> bool:
        return self._sub_store(person_id).remove(sub_id)

    # -- prefs / history --------------------------------------------------------

    def get_prefs(self, person_id: str) -> dict:
        return self._note_store(person_id).prefs()

    def put_prefs(self, person_id: str, prefs: dict) -> dict:
        return self._note_store(person_id).set_prefs(prefs)

    def list_notifications(self, person_id: str, unread: bool, limit: int) -> list[dict]:
        return self._note_store(person_id).list(unread, max(1, min(limit, 200)), self.now())

    def mark_read(self, person_id: str, note_id: str) -> bool:
        return self._note_store(person_id).mark_read(note_id, self.now())

    def read_all(self, person_id: str) -> int:
        return self._note_store(person_id).read_all(self.now())

    # -- rate limiting ----------------------------------------------------------

    def rate_limited(self, caller_id: str) -> bool:
        """30 publishes a minute per caller. In-process and per person:
        a restart clears it, which is fine for a courtesy limit."""
        now = self.now()
        with self._rate_lock:
            window = self._rate.setdefault(caller_id, deque())
            while window and now - window[0] >= 60:
                window.popleft()
            if len(window) >= RATE_LIMIT_PER_MINUTE:
                return True
            window.append(now)
            return False

    # -- the one publish path -----------------------------------------------------

    def notify(
        self,
        person_id: str,
        *,
        tier: str,
        source: str,
        title: str,
        body: str,
        link: str | None = None,
        dedupe_key: str | None = None,
        private: bool = False,
    ) -> dict:
        """Store first, then push. Returns {id, delivered, deferred, state}.

        ``private``: the Lock Screen shows only who sent it and "Open Worlds
        to read it."; the words stay in history (design: nothing private on
        the Lock Screen).

        ``state`` is one of: ``delivered`` (at least one device took
        it), ``failed`` (devices exist, none answered), ``no_devices``
        (nothing subscribed), ``not_configured`` (push is off here),
        ``deferred`` (quiet hours: it waits for the summary),
        ``history_only`` (the tier or source is off for this person),
        ``duplicate`` (this dedupe key already published today).
        """
        if tier not in TIERS:
            raise ValueError("tier is good_news, update or when_ready")
        store = self._note_store(person_id)
        now = self.now()
        if dedupe_key:
            hit = store.dedupe_hit(dedupe_key, now)
            if hit:
                return {"id": hit, "delivered": 0, "deferred": False, "state": "duplicate"}

        prefs = store.prefs()
        if not prefs["tiers"].get(tier, True) or prefs["sources"].get(source, True) is False:
            reason = "history_only"
        elif in_quiet_hours(prefs, now):
            reason = "deferred"
        else:
            reason = "push"

        note_id = uuid.uuid4().hex[:16]
        record = {
            "id": note_id,
            "tier": tier,
            "source": source,
            "title": title,
            "body": body,
            "link": link,
            "private": bool(private),
            "created_at": now,
            "read_at": None,
            "state": reason if reason != "push" else "pending",
        }
        store.add(record)
        if dedupe_key:
            store.dedupe_note(dedupe_key, note_id, now)

        if reason == "history_only":
            return {"id": note_id, "delivered": 0, "deferred": True, "state": "history_only"}
        if reason == "deferred":
            return {"id": note_id, "delivered": 0, "deferred": True, "state": "deferred"}
        if not self.configured():
            store.update_state(note_id, state="not_configured")
            return {"id": note_id, "delivered": 0, "deferred": False, "state": "not_configured"}

        delivered = self._push_person(person_id, record, urgency_for(tier))
        state = "delivered" if delivered > 0 else ("no_devices" if not self._sub_store(person_id).for_send() else "failed")
        store.update_state(note_id, state=state)
        return {"id": note_id, "delivered": delivered, "deferred": False, "state": state}

    def test_push(self, person_id: str) -> dict:
        """The Settings 'Send me a test': straight to the devices, past
        the prefs gates and quiet hours. The person just pressed the
        button, which is consent for this one; a test that waits until
        morning looks broken."""
        now = self.now()
        record = {
            "id": uuid.uuid4().hex[:16],
            "tier": "good_news",
            "source": "worlds",
            "title": "Worlds",
            "body": "🌳 The World Tree is awake. Everyone is home.",
            "link": "/",
            "created_at": now,
            "read_at": None,
            "state": "pending",
        }
        store = self._note_store(person_id)
        store.add(record)
        if not self.configured():
            store.update_state(record["id"], state="not_configured")
            return {"id": record["id"], "delivered": 0, "deferred": False, "state": "not_configured"}
        delivered = self._push_person(person_id, record, "normal")
        state = "delivered" if delivered > 0 else ("no_devices" if not self._sub_store(person_id).for_send() else "failed")
        store.update_state(record["id"], state=state)
        return {"id": record["id"], "delivered": delivered, "deferred": False, "state": state}

    # -- quiet-hours summary -------------------------------------------------

    def quiet_summaries(self) -> int:
        """One background tick: for every person whose quiet hours have
        ENDED and whose notifications waited, push a single line
        ("3 things waited for you"). Returns how many summaries went
        out. Never raises: a bad tick logs and the thread lives."""
        sent = 0
        try:
            ids = list(self.person_ids())
        except Exception as exc:  # pragma: no cover - defensive
            _logger.warning("push: person list failed: %s", type(exc).__name__)
            return 0
        for person_id in ids:
            try:
                store = self._note_store(person_id)
                if not store.path.exists():
                    continue
                prefs = store.prefs()
                if not (prefs["quiet_hours"].get("on")):
                    continue
                if in_quiet_hours(prefs, self.now()):
                    continue
                waiting = store.deferred()
                if not waiting:
                    continue
                n = len(waiting)
                words = "1 thing waited for you" if n == 1 else f"{n} things waited for you"
                now = self.now()
                summary = {
                    "id": uuid.uuid4().hex[:16],
                    "tier": "update",
                    "source": "quiet_summary",
                    "title": "Worlds",
                    "body": words,
                    "link": "/",
                    "created_at": now,
                    "read_at": None,
                    "state": "pending",
                }
                store.add(summary)
                delivered = self._push_person(person_id, summary, "normal") if self.configured() else 0
                store.update_state(summary["id"], state="delivered" if delivered else "quiet_summary")
                for rec in waiting:
                    store.update_state(rec["id"], state="summarized")
                if delivered:
                    sent += 1
            except Exception as exc:  # one bad person must not kill the tick
                _logger.warning(
                    "push: quiet summary for a person failed (%s)", type(exc).__name__
                )
        return sent

    # -- the wire -------------------------------------------------------------

    def _push_person(self, person_id: str, record: dict, urgency: str) -> int:
        """Send one notification to every device of one person. Returns
        the number of devices that accepted it. A device whose push
        service says it is gone (404/410) is removed; any other failure
        keeps the device and records short plain words."""
        private = bool(record.get("private"))
        payload = json.dumps(
            {
                "title": record["title"] if not private else "",
                "body": record["body"] if not private else "Open Worlds to read it.",
                "sender": sender_name(record.get("source")),
                "tier": record["tier"],
                "tier_words": TIER_WORDS.get(record["tier"], ""),
                "link": record.get("link"),
                "id": record["id"],
                "source": record.get("source"),
            }
        )
        vapid = self._vapid()
        if vapid is None:
            return 0
        claims = {"sub": self.subject()}
        store = self._sub_store(person_id)
        delivered = 0
        for sub in store.for_send():
            try:
                _webpush(
                    {"endpoint": sub["endpoint"], "keys": sub["keys"]},
                    data=payload,
                    vapid_private_key=vapid,
                    vapid_claims=claims,
                    ttl=TTL_SECONDS,
                    headers={"Urgency": urgency},
                    timeout=10,
                )
                delivered += 1
                store.mark_ok(sub["id"], self.now())
            except WebPushException as exc:
                code = getattr(exc, "status_code", None)
                if code in (404, 410):
                    store.remove(sub["id"])
                    _logger.info(
                        "push: a device left the push service (%s); it was removed",
                        code,
                    )
                    continue
                store.mark_error(sub["id"], f"push service refused ({code or 'error'})")
            except Exception:
                # A transport bug must not lose the notification (it is in
                # history) nor crash the request that triggered it.
                store.mark_error(sub["id"], "push failed (transport)")
        return delivered


def urgency_for(tier: str) -> str:
    """good_news/update ride at normal urgency; when_ready never wakes
    anyone — where it pushes at all, it is low urgency."""
    return "low" if tier == "when_ready" else "normal"
