"""C2 fetch seam for Worlds: one fetch per request, always classified, never raising.

The runner is the *only* thing that may reach the network, and it reaches it
through the confinement seam (``send``) and nothing else - no httpx, no urllib,
no sockets. Everything else here is bookkeeping:

* a write request, an unknown request or an unknown provider is refused before
  ``send`` is called at all;
* an in-memory TTL cache and a last-good record (in memory always, on disk when
  a ``cache_dir`` is given);
* single-flight per request id, so concurrent fetches share one send;
* classification into the C2 ``error_class`` words, with assertions;
* redaction of every note: secret values and ``Authorization``/``Bearer``/
  ``Basic`` credentials never survive into a :class:`Fetch`.

``fetch`` never raises: a failure is a :class:`Fetch` with ``ok=False`` and an
``error_class``. The response body is copied into a ``Fetch`` only as ``data``
on success - never into ``note``, never into evidence.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable

from . import mapping
from .confinement import ConfinementError, ErrorClass, RawResponse
from .models import send_scoped

__all__ = ["Fetch", "Runner", "redact", "REDACTED"]

logger = logging.getLogger(__name__)

#: What a redacted span is replaced with.
REDACTED = "[redacted]"
_MAX_NOTE = 300

#: How long a fetch that joined an in-flight send waits for it before trying alone.
_SHARE_TIMEOUT_S = 30.0

_REDACT_PATTERNS = (
    re.compile(r"Authorization:\s*\S+(?:\s+\S+)?"),
    re.compile(r"Bearer\s+\S+"),
    re.compile(r"Basic\s+\S+"),
)

_REQUEST_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}\.[a-z0-9][a-z0-9-]{0,62}$")


def redact(text: Any, secret_values: Iterable[str] = ()) -> str:
    """Return ``text`` with every secret value and credential pattern removed.

    Notes are the only place an upstream failure message can surface, so they
    pass through here before they are stored or shown. The result is flattened
    onto one line and capped at 300 characters.
    """
    if text is None:
        return ""
    out = str(text)
    for secret in secret_values or ():
        if isinstance(secret, str) and secret:
            out = out.replace(secret, REDACTED)
    for pattern in _REDACT_PATTERNS:
        out = pattern.sub(REDACTED, out)
    out = " ".join(out.split())
    return out[:_MAX_NOTE]


@dataclass(frozen=True)
class Fetch:
    """One classified attempt at one request. Never an exception, never a body."""

    request_id: str
    method: str | None = None
    path: str | None = None
    ok: bool = False
    data: Any = None
    error_class: ErrorClass | None = None
    status_code: int | None = None
    duration_ms: int | None = None
    fetched_at: float | None = None
    from_cache: bool = False
    #: Redacted, one line, at most 300 characters. Empty when there is nothing to say.
    note: str = ""

    def as_evidence(self) -> dict[str, Any]:
        """The C2 evidence object: request facts plus what went wrong, never a body."""
        evidence: dict[str, Any] = {
            "request_id": self.request_id,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "error_class": self.error_class,
        }
        if self.note:
            evidence["note"] = self.note
        return evidence


@dataclass
class _InFlight:
    """One shared send: whoever owns it sends, the rest wait on ``done``.

    An entry stays in the runner only while its send is running; a later arrival
    starts its own send (or a cache hit) rather than inheriting a stale result.
    """

    done: threading.Event = field(default_factory=threading.Event)
    result: Fetch | None = None

    @property
    def finished(self) -> bool:
        return self.done.is_set()


class Runner:
    """Fetch requests from the store, through the confinement seam, with cache and last-good."""

    def __init__(
        self,
        store: Any,
        send: Callable[..., Any],
        *,
        clock: Callable[[], float] = time.time,
        cache_dir: str | os.PathLike[str] | None = None,
        secret_values: Iterable[str] = (),
    ) -> None:
        self._store = store
        self._send = send
        self._clock = clock
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None
        self._secret_source = secret_values if secret_values is not None else ()   # read lazily at redaction time
        self._guard = threading.RLock()
        self._inflight: dict[str, _InFlight] = {}
        self._cache: dict[str, Fetch] = {}
        self._last_good: dict[str, tuple[Any, float]] = {}
        self._load_last_good()

    # -------------------------------------------------------------- public

    def fetch(self, request_id: str, *, force: bool = False) -> Fetch:
        """Fetch one request. Never raises; a failure is a Fetch with ``ok=False``."""
        request = self._get("request", request_id)
        if request is None:
            return self._failure(
                request_id,
                "confinement_denied",
                "unknown request: nothing was sent",
            )
        provider = self._get("provider", request.provider)
        if provider is None:
            return self._failure(
                request_id,
                "confinement_denied",
                f"unknown provider {request.provider!r}: nothing was sent",
                method=request.method,
                path=request.path,
            )
        if request.resolved_effect() == "write":
            return self._failure(
                request_id,
                "confinement_denied",
                "write effect: refused before send (a card fetch never performs a write)",
                method=request.method,
                path=request.path,
            )

        flight, owner = self._join(request_id)
        if not owner:
            shared = flight.result
            return replace(shared, from_cache=True) if shared is not None else self._failure(
                request_id,
                "connection",
                "the shared fetch produced no result",
                method=request.method,
                path=request.path,
            )

        result: Fetch | None = None
        try:
            if not force:
                # Re-check on entry: a send that just finished may have filled it.
                cached = self._fresh_cache(request_id, request)
                if cached is not None:
                    result = replace(cached, from_cache=True)
                    return result
            result = self._send_once(request_id, provider, request)
            if result.ok:
                self._remember(request_id, request, result)
            return result
        finally:
            self._leave(request_id, flight, result)

    def last_good(self, request_id: str) -> tuple[Any, float] | None:
        """``(data, fetched_at)`` of the most recent success, or None."""
        with self._guard:
            return self._last_good.get(request_id)

    # ------------------------------------------------------------ internal

    def _get(self, kind: str, obj_id: Any) -> Any:
        try:
            return self._store.get(kind, obj_id)
        except Exception:  # a store that refuses the id reads the same as "not configured"
            logger.exception("worlds store refused a lookup for %s %r", kind, obj_id)
            return None

    def _join(self, request_id: str) -> tuple[_InFlight, bool]:
        """Own the send for this request, or wait on the one already running."""
        with self._guard:
            flight = self._inflight.get(request_id)
            if flight is None:
                flight = _InFlight()
                self._inflight[request_id] = flight
                return flight, True
        while True:
            flight.done.wait(_SHARE_TIMEOUT_S)
            if flight.result is not None:
                return flight, False
            with self._guard:
                if self._inflight.get(request_id) is flight:
                    # The owner never published (crashed, or hung): take over.
                    del self._inflight[request_id]
                    return self._join(request_id)

    def _leave(self, request_id: str, flight: _InFlight, result: Fetch | None) -> None:
        with self._guard:
            flight.result = result
            if self._inflight.get(request_id) is flight:
                del self._inflight[request_id]
        flight.done.set()

    def _failure(
        self,
        request_id: str,
        error_class: ErrorClass,
        note: str,
        *,
        method: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
        duration_ms: int | None = None,
        fetched_at: float | None = None,
    ) -> Fetch:
        return Fetch(
            request_id=request_id,
            method=method,
            path=path,
            ok=False,
            error_class=error_class,
            status_code=status_code,
            duration_ms=duration_ms,
            fetched_at=self._clock() if fetched_at is None else fetched_at,
            note=self._redact(note),
        )

    def _redact(self, text: Any) -> str:
        return redact(text, tuple(self._secret_source))

    def _send_once(self, request_id: str, provider: Any, request: Any) -> Fetch:
        now = self._clock()
        try:
            response = send_scoped(self._send, provider, request, effect="read")
        except Exception as exc:
            return self._failure(
                request_id,
                "connection",
                f"{type(exc).__name__}: {exc}",
                method=request.method,
                path=request.path,
                fetched_at=now,
            )
        if isinstance(response, ConfinementError):
            return Fetch(
                request_id=request_id,
                method=request.method,
                path=request.path,
                ok=False,
                error_class=response.error_class,
                status_code=response.status_code,
                duration_ms=response.duration_ms,
                fetched_at=now,
                note=self._redact(response.note),
            )
        if not isinstance(response, RawResponse):
            return self._failure(
                request_id,
                "connection",
                f"send returned {type(response).__name__}, not a response",
                method=request.method,
                path=request.path,
                fetched_at=now,
            )
        return self._classify(request_id, request, response, now)

    def _classify(self, request_id: str, request: Any, response: RawResponse, now: float) -> Fetch:
        status = response.status_code
        facts: dict[str, Any] = {
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "status_code": status,
            "duration_ms": response.duration_ms,
            "fetched_at": now,
        }
        if status in (401, 403):
            return Fetch(**facts, ok=False, error_class="auth_failed")
        if 400 <= status < 500:
            return Fetch(**facts, ok=False, error_class="http_4xx")
        if status >= 500:
            return Fetch(**facts, ok=False, error_class="http_5xx")

        data = self._parse_body(response.body)
        if isinstance(data, str):
            return Fetch(**facts, ok=False, error_class="malformed", note=self._redact(data))

        failed = self._check_assertions(request, response, data)
        if failed:
            return Fetch(**facts, ok=False, error_class="malformed", note=self._redact(failed))

        return Fetch(**facts, ok=True, data=data)

    @staticmethod
    def _parse_body(body: bytes) -> Any:
        """The parsed JSON, or a short reason the body is not usable JSON."""
        try:
            text = bytes(body or b"").decode("utf-8")
        except (UnicodeDecodeError, AttributeError, TypeError):
            return "response body is not valid UTF-8"
        try:
            return json.loads(text)
        except ValueError:
            return "response body is not valid JSON"

    def _check_assertions(self, request: Any, response: RawResponse, data: Any) -> str | None:
        """The first assertion that does not hold, or None when they all hold."""
        for assertion in getattr(request, "assertions", []) or []:
            if assertion.status is not None and assertion.status != response.status_code:
                return (
                    f"assertion failed: status is {response.status_code}, "
                    f"expected {assertion.status}"
                )
            if assertion.path is None:
                continue
            try:
                res = mapping.resolve(data, assertion.path)
            except mapping.MappingError as exc:
                return f"assertion failed: {exc}"
            found = res.values
            if assertion.exists and not res.found:
                return f"assertion failed: {assertion.path} is missing"
            if assertion.is_list and (not found or not all(isinstance(value, list) for value in found)):
                return f"assertion failed: {assertion.path} is not a list"
            if assertion.equals is not None and found != [assertion.equals]:
                return f"assertion failed: {assertion.path} is not the expected value"
        return None

    # --------------------------------------------------------------- cache

    def _fresh_cache(self, request_id: str, request: Any) -> Fetch | None:
        """The cached fetch for this request if one exists and its TTL has not run out."""
        ttl = getattr(request, "ttl_s", 0)
        if not isinstance(ttl, (int, float)) or ttl <= 0:
            return None
        with self._guard:
            cached = self._cache.get(request_id)
            if cached is None or cached.fetched_at is None:
                return None
            if self._clock() - cached.fetched_at >= ttl:
                del self._cache[request_id]
                return None
            return cached

    def _remember(self, request_id: str, request: Any, result: Fetch) -> None:
        """Record a success as last-good, and as the TTL cache entry when it has one."""
        with self._guard:
            self._last_good[request_id] = (result.data, result.fetched_at)
            ttl = getattr(request, "ttl_s", 0)
            if isinstance(ttl, (int, float)) and ttl > 0:
                self._cache[request_id] = result
        if self._cache_dir is not None:
            self._write_last_good(request_id, result.data, result.fetched_at)

    # ----------------------------------------------------------- last-good

    def _last_good_path(self, request_id: str) -> Path | None:
        if self._cache_dir is None or not isinstance(request_id, str):
            return None
        if not _REQUEST_ID_RE.match(request_id):
            return None  # never build a path from an unvalidated id
        return self._cache_dir / f"{request_id}.json"

    def _write_last_good(self, request_id: str, data: Any, fetched_at: float | None) -> None:
        path = self._last_good_path(request_id)
        if path is None:
            return
        payload = json.dumps(
            {"request_id": request_id, "fetched_at": fetched_at, "data": data},
            default=str,
        ).encode("utf-8")
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                os.chmod(path.parent, 0o700)
            except OSError:  # a shared cache root may not be ours to tighten
                logger.debug("could not tighten cache dir mode: %s", path.parent)
            fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
            tmp = Path(tmp_name)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(tmp, 0o600)
                os.replace(tmp, path)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
        except OSError:
            # Last-good on disk is disposable; losing it must not lose the fetch.
            logger.exception("could not write last-good for %s", request_id)

    def _load_last_good(self) -> None:
        """Adopt any last-good already on disk: the cache dir is disposable, not authoritative."""
        if self._cache_dir is None or not self._cache_dir.is_dir():
            return
        for path in sorted(self._cache_dir.glob("*.json")):
            request_id = path.name[: -len(".json")]
            if not _REQUEST_ID_RE.match(request_id):
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(raw, dict) or raw.get("request_id") != request_id:
                continue
            fetched_at = raw.get("fetched_at")
            if not isinstance(fetched_at, (int, float)):
                continue
            with self._guard:
                self._last_good.setdefault(request_id, (raw.get("data"), float(fetched_at)))
