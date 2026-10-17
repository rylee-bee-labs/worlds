"""Outbound confinement: the ONLY way Worlds sends a request to a provider.

Contract: docs/rebuild/CONTRACTS.md (C1 provider limits, C2 error classes). Every outbound
request goes through ``confined_request``; nothing else in ``personal_world.worlds`` may open a
socket. What this module guarantees for each call:

* **Resolve, then connect pinned.** The host is resolved once; every answer is classified; the
  connection goes to one of the vetted addresses by IP literal (TLS still verifies the original
  hostname through SNI/verification), so a second DNS answer can never redirect the request.
* **Deny by address class.** Loopback, link-local, private (RFC1918, CGNAT, ULA), unspecified,
  multicast and reserved addresses are refused unless the provider is marked ``network.lan``.
  Cloud metadata addresses are refused even then. If ANY answer is denied, the call is denied.
* **No redirects, no retries, no proxies, no env trust.** A 3xx is ``redirect_refused``.
* **Size and time caps.** ``max_bytes`` (declared and streamed) and one total deadline per call.
* **URL safety.** The joined URL must keep the provider's scheme, host and port; hop-by-hop and
  framing headers and CR/LF in header values are refused; Authorization/Cookie are never taken
  from the request (only injected from the provider's secret reference).
* A read effect may not carry a mutating method.

``cookie_session`` and ``password_grant`` add one exchange, not a weaker path: the login/token POST
is joined and re-checked like any request path, dials the same pinned address, and spends the SAME
single deadline. The issued cookie/token lives only in this process's memory, keyed by the whole
provider identity, and is attached to that provider's requests only. A refused read re-logs-in once
and replays once; a refused write is never replayed (ADR-0008: no automatic side-effect retries).

Secret values are injected here and never put into errors, notes or logs.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from urllib.parse import quote, urlencode, urlsplit

import httpcore
import httpx

from .secrets import resolve_secret_ref
from .templates import render_query

ErrorClass = Literal[
    "timeout",
    "connection",
    "http_4xx",
    "http_5xx",
    "malformed",
    "redirect_refused",
    "too_large",
    "confinement_denied",
    "auth_failed",
]


@dataclass(frozen=True)
class RawResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    duration_ms: int = 0


@dataclass(frozen=True)
class ConfinementError:
    error_class: ErrorClass
    note: str = ""
    status_code: int | None = None
    duration_ms: int | None = None
    # True when NOTHING was sent (refused, unresolved, no credential): the action provably did not run.
    pre_send: bool = False


_METADATA = {
    ipaddress.ip_address("169.254.169.254"),  # pw-safety: synthetic
    ipaddress.ip_address("169.254.170.2"),  # pw-safety: synthetic
    ipaddress.ip_address("100.100.100.200"),
    ipaddress.ip_address("fd00:ec2::254"),
    ipaddress.ip_address("168.63.129.16"),  # Azure wire server / metadata
}
_CGNAT = ipaddress.ip_network("100.64.0.0/10")
_NEVER = (ipaddress.ip_network("0.0.0.0/8"), ipaddress.ip_network("240.0.0.0/4"))
_FORBIDDEN_HEADERS = {
    "host", "content-length", "transfer-encoding", "connection", "upgrade", "te", "trailer",
    "keep-alive", "proxy-authorization", "proxy-connection", "authorization", "cookie", "set-cookie",
    "expect",
}
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
#: Auth kinds that hold a live credential in this process's memory (C1). Every other kind is a header
#: injected straight from the provider's secret reference and never needs a login exchange.
_SESSION_AUTH = ("cookie_session", "password_grant")

Resolver = Callable[[str, int], list[str]]


def _system_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    out: list[str] = []
    for info in infos:
        addr = info[4][0]
        if addr not in out:
            out.append(addr)
    return out


_SITE_LOCAL = ipaddress.ip_network("fec0::/10")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_6TO4 = ipaddress.ip_network("2002::/16")
_TEREDO = ipaddress.ip_network("2001::/32")


def _embedded_v4(ip: ipaddress.IPv6Address) -> list[ipaddress.IPv4Address]:
    """IPv4 addresses hidden inside an IPv6 one (mapped, NAT64, 6to4, Teredo)."""
    found: list[ipaddress.IPv4Address] = []
    if ip.ipv4_mapped is not None:
        found.append(ip.ipv4_mapped)
    raw = ip.packed
    if ip in _NAT64:
        found.append(ipaddress.IPv4Address(raw[12:16]))
    if ip in _6TO4:
        found.append(ipaddress.IPv4Address(raw[2:6]))
    if ip in _TEREDO:
        found.append(ipaddress.IPv4Address(raw[4:8]))                                   # server
        found.append(ipaddress.IPv4Address(bytes(b ^ 0xFF for b in raw[12:16])))        # client (obfuscated)
    return found


def classify_address(address: str, *, lan: bool) -> str | None:
    """Return None when allowed, else a short reason. Uses the RESOLVED address, never the text."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return "unparseable address"
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = _embedded_v4(ip)
        for v4 in embedded:  # a metadata/unroutable IPv4 hidden in IPv6 is refused even with lan
            inner = classify_address(str(v4), lan=lan)
            if inner and ("metadata" in inner or "unroutable" in inner):
                return inner
        if embedded and not lan:
            for v4 in embedded:
                inner = classify_address(str(v4), lan=False)
                if inner:
                    return inner
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
    if ip in _METADATA:
        return "cloud metadata address"
    if ip.is_unspecified or ip.is_multicast:
        return "unroutable address"
    if isinstance(ip, ipaddress.IPv4Address) and any(ip in n for n in _NEVER):
        return "unroutable address"
    internal = (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or (isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT)
        or (isinstance(ip, ipaddress.IPv6Address) and ip in _SITE_LOCAL)
    )
    if ip.is_reserved and not internal:  # ::1 is "reserved" to ipaddress but is loopback
        return "unroutable address"
    if internal and not lan:
        return "internal address (provider is not marked lan)"
    return None


def _deny(note: str, started: float | None = None) -> ConfinementError:
    return ConfinementError("confinement_denied", note, duration_ms=_ms(started), pre_send=True)


def _ms(started: float | None) -> int | None:
    return None if started is None else int((time.monotonic() - started) * 1000)


def build_url(provider: Any, request: Any, now: Any = None) -> tuple[str, str, int, str] | str:
    """Return (scheme, host, port, path_and_query) or a refusal reason (str).

    Query values may carry the closed set of C1.3 templates ({today}, {today+Nd}, {today-Nd}, {now}); they are
    rendered here, in UTC, and nowhere else.
    """
    base = urlsplit(provider.base_url)
    if base.scheme not in ("http", "https") or not base.hostname:
        return "provider base_url must be http(s) with a host"
    if base.username is not None or base.password is not None or base.fragment or base.query:
        return "provider base_url must not carry userinfo, query or fragment"
    try:
        port = base.port or (443 if base.scheme == "https" else 80)
    except ValueError:
        return "provider base_url has an invalid port"
    if port == 0:
        return "port 0 is not allowed"
    path = request.path
    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or path.startswith("//")
        or "\\" in path
        or "@" in path.split("?")[0]
        or any(c in path for c in ("\r", "\n", "\t", " ", "#"))
        or "?" in path
    ):
        return "request path is not a plain relative path"
    segments = path.split("/")
    low = path.lower()
    if ".." in segments or "." in segments or "%2e" in low or "%2f" in low or "%5c" in low or "%00" in low:
        return "request path escapes its prefix"
    prefix = (provider.path_prefix or "").rstrip("/")
    if prefix and (".." in prefix.split("/") or "\\" in prefix or "://" in prefix):
        return "provider path_prefix is not safe"
    base_path = base.path.rstrip("/")
    full_path = f"{base_path}{prefix}{path}"
    query = urlencode(render_query(request.query, now), quote_via=quote) if request.query else ""
    joined = f"{base.scheme}://{base.netloc}{full_path}" + (f"?{query}" if query else "")
    check = urlsplit(joined)
    if (check.scheme, check.hostname, check.port or port) != (base.scheme, base.hostname, port):
        return "joined URL changed the provider destination"
    return base.scheme, base.hostname, port, full_path + (f"?{query}" if query else "")


def _auth_headers(provider: Any) -> dict[str, str] | ConfinementError:
    auth = provider.auth
    if auth.type == "none":
        return {}
    value = resolve_secret_ref(auth.secret_ref)
    if not value:
        return ConfinementError("auth_failed", "credential is not available", pre_send=True)
    try:
        value.encode("ascii")  # header values go out as latin-1 at best; only ASCII is safe everywhere
    except UnicodeEncodeError:
        return ConfinementError("auth_failed", "credential contains characters that cannot be sent", pre_send=True)
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return ConfinementError("auth_failed", "credential contains control characters", pre_send=True)
    if auth.type == "bearer":
        return {"Authorization": f"Bearer {value}"}
    if auth.type == "header":
        from .models import check_auth_header_name

        try:
            check_auth_header_name(auth.header_name or "")
        except ValueError:
            return ConfinementError("confinement_denied", "credential header name is not allowed", pre_send=True)
        return {auth.header_name: value}
    if auth.type == "basic":
        return {"Authorization": "Basic " + base64.b64encode(value.encode()).decode()}
    return ConfinementError("auth_failed", "unknown auth type")


# ---------------------------------------------------------------------------------------------
# cookie_session / password_grant: a live credential that only ever exists in this process's memory.
# ---------------------------------------------------------------------------------------------

#: provider identity -> the ``name=value`` session cookie or the bearer token. Bounded: a process
#: that talks to many providers keeps at most this many live credentials and drops the oldest.
_SESSION_MAX = 256
_SESSIONS: dict[tuple[str, ...], str] = {}
_SESSION_LOCK = threading.Lock()


def _session_key(provider: Any) -> tuple[str, ...]:
    """Everything a held credential belongs to.

    The key carries the destination AND the credential identity, so editing a provider's
    ``base_url``, ``path_prefix``, ``secret_ref`` or login/token path makes a NEW key: a session
    obtained under the old config can never be sent to a new destination or under a new secret.
    """
    auth = provider.auth
    return (
        str(getattr(provider, "id", "")),
        str(getattr(provider, "base_url", "")),
        str(getattr(provider, "path_prefix", "")),
        str(getattr(auth, "type", "")),
        str(getattr(auth, "secret_ref", "")),
        str(getattr(auth, "login_path", "") or ""),
        str(getattr(auth, "token_path", "") or ""),
    )


def _session_take(key: tuple[str, ...]) -> str | None:
    with _SESSION_LOCK:
        return _SESSIONS.get(key)


def _session_keep(key: tuple[str, ...], credential: str) -> None:
    with _SESSION_LOCK:
        if key not in _SESSIONS and len(_SESSIONS) >= _SESSION_MAX:
            _SESSIONS.pop(next(iter(_SESSIONS)), None)  # bounded: the oldest entry goes
        _SESSIONS[key] = credential


def _session_forget(key: tuple[str, ...]) -> None:
    with _SESSION_LOCK:
        _SESSIONS.pop(key, None)


def _auth_pair(auth: Any) -> tuple[str, str] | ConfinementError:
    """``(username, password)`` from the ONE secret that carries both, or the failure.

    The value is never echoed: a note names the secret REF, and the same ASCII/control-character
    rules ``_auth_headers`` applies to a header credential apply before the pair is ever encoded.
    """
    ref = getattr(auth, "secret_ref", None) or "(unset)"
    value = resolve_secret_ref(getattr(auth, "secret_ref", None))
    if not value:
        return ConfinementError("auth_failed", f"credential for {ref} is not available", pre_send=True)
    try:
        value.encode("ascii")  # a form body is no safer than a header value
    except UnicodeEncodeError:
        return ConfinementError("auth_failed", f"credential for {ref} contains characters that cannot be sent",
                                pre_send=True)
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return ConfinementError("auth_failed", f"credential for {ref} contains control characters", pre_send=True)
    username, sep, password = value.partition(":")
    if not sep or not username or not password:
        return ConfinementError("auth_failed", f"credential for {ref} must be username:password", pre_send=True)
    return username, password


def _cookie_pair(set_cookie: str | None) -> str | None:
    """The ``name=value`` of a Set-Cookie header. Its attributes (Path, HttpOnly, ...) never travel."""
    if not set_cookie:
        return None
    pair = set_cookie.split(";", 1)[0].strip()
    return _holdable(pair)


def _holdable(value: str) -> str | None:
    """Refuse an issued credential we could not put in a header verbatim. Nothing is stored."""
    if not value or len(value) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value


class _AuthEndpoint:
    """A bare path probe: ``build_url`` vets it exactly like a request path, so the login/token
    endpoint is joined under the same base_url + path_prefix and re-checked against the same
    scheme, host and port. It carries no query, no headers and no body the caller supplied."""

    __slots__ = ("path", "query")

    def __init__(self, path: str) -> None:
        self.path = path
        self.query: dict[str, str] = {}


class _Ready:
    """A request that passed every guard, pinned to one vetted address, ready to be written."""

    __slots__ = ("scheme", "host", "port", "pinned", "target", "headers")

    def __init__(self, scheme: str, host: str, port: int, pinned: str, target: str,
                 headers: dict[str, str]) -> None:
        self.scheme = scheme
        self.host = host
        self.port = port
        self.pinned = pinned
        self.target = target
        self.headers = headers


class Deadline:
    """ONE wall-clock budget for a whole call: DNS, connect, TLS, headers and body.

    A timer fires at the budget and shuts down every socket the call opened (by dup'd descriptor, so
    TLS-wrapped sockets are covered too), which unblocks any read or write. Disarm it before the
    sockets are closed so a late fire can never touch a recycled descriptor.
    """

    def __init__(self, budget: float):
        self.budget = float(budget)
        self.started = time.monotonic()
        self.expired = threading.Event()
        self._lock = threading.Lock()
        self._fds: set[int] = set()
        self._done = False
        self._timer = threading.Timer(self.budget, self._fire)
        self._timer.daemon = True
        self._timer.start()

    def remaining(self) -> float:
        return self.budget - (time.monotonic() - self.started)

    def register(self, fd: int) -> None:
        with self._lock:
            if not self._done:
                self._fds.add(fd)

    def unregister(self, fd: int) -> None:
        """Called when a stream closes, BEFORE the descriptor number can be reused."""
        with self._lock:
            self._fds.discard(fd)

    def _fire(self) -> None:
        with self._lock:
            if self._done:
                return
            self.expired.set()
            for fd in self._fds:
                try:
                    dup = socket.socket(fileno=os.dup(fd))
                except OSError:
                    continue
                try:
                    dup.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                finally:
                    dup.close()

    def disarm(self) -> None:
        with self._lock:
            self._done = True
            self._fds.clear()
        self._timer.cancel()

    def rearm(self) -> None:
        """Restart the watchdog for the NEXT exchange of the same call.

        ``perform`` disarms the deadline when its exchange ends, so a call that needs a second
        exchange (the login POST, then the request it serves; then a re-login and one replay) must
        say so explicitly. The start time and the total budget are untouched: every exchange in a
        call still shares ONE wall-clock deadline, and no fds from a closed exchange are re-armed.
        """
        with self._lock:
            if not self._done:
                return
            self._done = False
            self._timer = threading.Timer(max(self.remaining(), 0.0), self._fire)
            self._timer.daemon = True
            self._timer.start()

    close = disarm


def _track(stream: Any, deadline: "Deadline", fd: int) -> Any:
    """Make ``stream`` (and the TLS stream it may turn into) unregister its fd the moment it closes,
    and clamp TLS-handshake time to what is left of the budget."""
    original_close = stream.close
    original_tls = stream.start_tls

    def close() -> None:
        deadline.unregister(fd)  # first: once closed, the number may belong to someone else
        original_close()

    def start_tls(ssl_context, server_hostname=None, timeout=None):
        left = max(deadline.remaining(), 0.01)
        tls = original_tls(ssl_context, server_hostname=server_hostname, timeout=min(timeout, left) if timeout else left)
        return _track(tls, deadline, fd)

    stream.close = close
    stream.start_tls = start_tls
    return stream


class _WatchedBackend(httpcore.SyncBackend):
    """Registers each new connection with the deadline so the watchdog can shut it down, applies the
    remaining budget to connect, and unregisters the descriptor when the stream closes."""

    def __init__(self, deadline: Deadline):
        self._deadline = deadline

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        left = max(self._deadline.remaining(), 0.01)
        stream = super().connect_tcp(host, port, timeout=min(timeout, left) if timeout else left,
                                     local_address=local_address, socket_options=socket_options)
        sock = stream.get_extra_info("socket")
        if sock is None:
            return stream
        fd = sock.fileno()
        self._deadline.register(fd)
        if self._deadline.expired.is_set():
            self._deadline.unregister(fd)
            stream.close()
            raise httpcore.ConnectTimeout("deadline passed while connecting")
        return _track(stream, self._deadline, fd)


class _WatchedTransport(httpx.HTTPTransport):
    """httpx transport whose connection pool reports its sockets to a :class:`Deadline`."""

    def __init__(self, deadline: Deadline, *, verify: bool):
        super().__init__(verify=verify, retries=0, limits=httpx.Limits(max_keepalive_connections=0))
        self._pool.close()
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(verify=verify, trust_env=False),
            max_connections=1, max_keepalive_connections=0, http1=True, http2=False, retries=0,
            network_backend=_WatchedBackend(deadline),
        )


_DNS_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="worlds-dns")
_DNS_PER_PROVIDER = 2
_dns_slots: dict[str, threading.BoundedSemaphore] = {}
_dns_lock = threading.Lock()


def _dns_slot(key: str) -> threading.BoundedSemaphore:
    with _dns_lock:
        return _dns_slots.setdefault(key, threading.BoundedSemaphore(_DNS_PER_PROVIDER))


def resolve_within(resolver: Resolver, host: str, port: int, deadline: Deadline, key: str = "") -> list[str] | ConfinementError:
    """DNS on a small shared pool with at most two lookups in flight per provider, so a hostile or slow
    resolver can neither outlive the budget, pile up threads, nor starve other providers' lookups.
    Nothing has been sent when a lookup fails or times out, so every failure here is ``pre_send``."""
    slot = _dns_slot(key or host)
    if not slot.acquire(blocking=False):
        return ConfinementError("timeout", "too many name lookups in flight for this provider",
                                duration_ms=_ms(deadline.started), pre_send=True)

    def run() -> list[str]:
        try:
            return resolver(host, port)
        finally:
            slot.release()

    future = _DNS_POOL.submit(run)
    try:
        addresses = future.result(timeout=max(deadline.remaining(), 0.0))
    except FutureTimeout:
        if future.cancel():  # it never started: nothing will release the slot, so do it here
            slot.release()
        return ConfinementError("timeout", "name lookup did not finish in time", duration_ms=_ms(deadline.started), pre_send=True)
    except Exception:  # a failed or broken lookup
        return ConfinementError("connection", "host did not resolve", duration_ms=_ms(deadline.started), pre_send=True)
    if not addresses:
        return ConfinementError("connection", "host did not resolve", duration_ms=_ms(deadline.started), pre_send=True)
    return list(addresses)


def confined_request(
    provider: Any,
    request: Any,
    *,
    effect: Literal["read", "write"],
    resolver: Resolver | None = None,
    in_scope: bool = True,
) -> RawResponse | ConfinementError:
    """Send one request. Never retries, never follows redirects, never raises.

    ``in_scope`` is the call site's verdict on the credential's scope (a decision about capabilities, which is
    Worlds' meaning, not the transport's). The transport only enforces it: False is ``auth_failed`` before DNS.
    """
    try:
        budget = float(request.timeout_s or provider.timeout_s)
    except Exception:
        return ConfinementError("connection", "internal error: bad request or provider")
    deadline = Deadline(budget)
    try:
        return _send(provider, request, effect, resolver or _system_resolver, deadline, in_scope)
    except Exception as exc:  # a bug here must fail closed, with no secret in the note
        return ConfinementError("connection", f"internal error: {type(exc).__name__}", duration_ms=_ms(deadline.started))
    finally:
        deadline.disarm()


def _send(provider: Any, request: Any, effect: str, resolver: Resolver, deadline: Deadline, in_scope: bool = True):
    ready = _prepare(provider, request, effect, resolver, deadline, in_scope)
    if isinstance(ready, ConfinementError):
        return ready
    if getattr(provider.auth, "type", "none") in _SESSION_AUTH:
        return _session_send(provider, request, ready, effect, deadline)
    auth = _auth_headers(provider)
    if isinstance(auth, ConfinementError):
        return auth
    return _exchange(ready, provider, request, deadline, auth)


def _prepare(provider: Any, request: Any, effect: str, resolver: Resolver, deadline: Deadline, in_scope: bool = True):
    """Every guard that must pass before a single byte goes out; returns the pinned request or why not."""
    started = deadline.started
    method = request.method.upper()
    if effect not in ("read", "write"):
        return _deny("unknown effect", started)
    if effect == "read" and method in _MUTATING:
        return _deny("a read effect cannot send a mutating method", started)

    built = build_url(provider, request)
    if isinstance(built, str):
        return _deny(built, started)
    scheme, host, port, target = built

    headers: dict[str, str] = {}
    for name, value in request.headers.items():
        if name.lower() in _FORBIDDEN_HEADERS:
            return _deny(f"header {name!r} is not allowed", started)
        if any(c in f"{name}{value}" for c in ("\r", "\n", "\x00")):
            return _deny("header contains a control character", started)
        headers[name] = value

    if not in_scope:  # the call site's verdict; before DNS: an out-of-scope capability costs no lookup and no bytes
        return ConfinementError("auth_failed", "capability is outside the credential's scope", duration_ms=_ms(started),
                                pre_send=True)

    addresses = resolve_within(resolver, host, port, deadline, key=str(getattr(provider, 'id', '')))
    if isinstance(addresses, ConfinementError):
        return addresses
    lan = bool(provider.network.lan)
    for address in addresses:
        reason = classify_address(address, lan=lan)
        if reason:
            return _deny(reason, started)
    pinned = addresses[0]

    principal = getattr(provider, "principal_id", None)
    if provider.kind == "room0" and principal:
        # Worlds speaks for one named person, from the provider's validated setting: never a request header.
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", principal):
            return _deny("principal_id is not valid", started)
        headers["X-Worlds-Principal"] = principal

    headers["Host"] = _host_header(scheme, host, port)
    headers["Connection"] = "close"
    headers.setdefault("Accept", "application/json")
    return _Ready(scheme, host, port, pinned, target, headers)


def _host_header(scheme: str, host: str, port: int) -> str:
    host_text = f"[{host}]" if ":" in host else host
    return f"{host_text}:{port}" if _nondefault(scheme, port) else host_text


def _exchange(ready: _Ready, provider: Any, request: Any, deadline: Deadline,
              credential: dict[str, str] | None) -> RawResponse | ConfinementError:
    """Write one prepared request, carrying ``credential`` (a cookie or a bearer token) from memory.

    The credential is added here, after the caller's own headers were vetted, so it is never part of
    ``request.headers`` and never reaches a note, a log line or a returned response.
    """
    if deadline.expired.is_set() or deadline.remaining() <= 0:
        return ConfinementError("timeout", "total time budget exceeded", duration_ms=_ms(deadline.started))
    headers = dict(ready.headers)
    if credential:
        headers.update(credential)
    body = None
    method = request.method.upper()
    if request.body is not None and method not in ("GET", "HEAD"):
        body = json.dumps(request.body).encode()
        headers.setdefault("Content-Type", "application/json")
    return _write(ready, provider, deadline, method, ready.target, headers, body)


def _write(ready: _Ready, provider: Any, deadline: Deadline, method: str, target: str,
           headers: dict[str, str], body: bytes | None) -> RawResponse | ConfinementError:
    """One exchange to the pinned address under the call's deadline and caps (no redirects, no retry)."""
    if deadline.expired.is_set() or deadline.remaining() <= 0:
        return ConfinementError("timeout", "total time budget exceeded", duration_ms=_ms(deadline.started))
    deadline.rearm()  # perform() disarms when an exchange ends; the next one shares the same deadline
    literal = f"[{ready.pinned}]" if ":" in ready.pinned else ready.pinned
    url = f"{ready.scheme}://{literal}:{ready.port}{target}"
    extensions = {"sni_hostname": ready.host} if ready.scheme == "https" else {}
    return perform(deadline, method, url, headers=headers, content=body, extensions=extensions,
                   verify=bool(provider.tls_verify), limit=int(provider.max_bytes))


def _session_send(provider: Any, request: Any, ready: _Ready, effect: str, deadline: Deadline):
    """A ``cookie_session`` or ``password_grant`` call: log in (once), send, refresh at most once.

    A refusal (403 for a session, 401 for a token) drops the stale credential. It is re-obtained and
    the SAME request is replayed ONLY when the effect is a read; a write-like request is returned as
    the refusal it is, because a side effect is never retried automatically (ADR-0008, handoff §7).
    """
    auth = provider.auth
    cookie = auth.type == "cookie_session"
    refusal = 403 if cookie else 401
    path = auth.login_path if cookie else auth.token_path
    key = _session_key(provider)

    held = _session_take(key)
    if held is None:
        held, error = _authenticate(provider, ready, deadline, cookie)
        if error is not None:
            return error
        _session_keep(key, held)
    response = _exchange(ready, provider, request, deadline, _credential_header(auth, held, cookie))
    if not (isinstance(response, RawResponse) and response.status_code == refusal):
        return response

    _session_forget(key)  # stale either way: the next call logs in fresh
    if effect != "read":
        return response
    held, error = _authenticate(provider, ready, deadline, cookie)
    if error is not None:
        return error  # a failed re-login is a failure, never a swallowed success
    _session_keep(key, held)
    response = _exchange(ready, provider, request, deadline, _credential_header(auth, held, cookie))
    if isinstance(response, RawResponse) and response.status_code == refusal:
        return ConfinementError("auth_failed", f"{'session' if cookie else 'token'} refused at {path}",
                                status_code=response.status_code, duration_ms=response.duration_ms)
    return response


def _credential_header(auth: Any, credential: str, cookie: bool) -> dict[str, str]:
    return {"Cookie": credential} if cookie else {"Authorization": f"Bearer {credential}"}


def _authenticate(provider: Any, ready: _Ready, deadline: Deadline,
                  cookie: bool) -> tuple[str | None, ConfinementError | None]:
    """Run the login/token exchange and return the credential to hold, or the failure.

    The exchange is built from the Auth block alone -- no caller header, query or body travels in
    it -- and it is written like any other request: same joined-and-rechecked destination, same
    pinned address, same deadline, same ``max_bytes``, no redirect followed.
    """
    auth = provider.auth
    path = auth.login_path if cookie else auth.token_path
    label = "login" if cookie else "token"
    pair = _auth_pair(auth)
    if isinstance(pair, ConfinementError):
        return None, pair
    if deadline.expired.is_set() or deadline.remaining() <= 0:
        return None, ConfinementError("timeout", "total time budget exceeded", duration_ms=_ms(deadline.started))
    if not isinstance(path, str) or not path:
        return None, ConfinementError("auth_failed", f"{label} path is not configured", pre_send=True)

    built = build_url(provider, _AuthEndpoint(path))
    if isinstance(built, str):
        return None, _deny(built, deadline.started)
    scheme, host, port, target = built
    if (scheme, host, port) != (ready.scheme, ready.host, ready.port):
        # build_url already re-checks the joined destination; this is the second lock on the one the
        # request itself was pinned to, so the credential can only ever go where the request would.
        return None, _deny(f"{label} path is not on the provider's destination", deadline.started)

    body = urlencode({auth.username_field: pair[0], auth.password_field: pair[1]}).encode()
    # Built from the Auth block alone: nothing the caller's request carried (header, query, body,
    # principal) rides along on the credential exchange.
    headers = {
        "Host": _host_header(ready.scheme, ready.host, ready.port),
        "Connection": "close",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    response = _write(ready, provider, deadline, "POST", target, headers, body)
    if isinstance(response, ConfinementError):
        return None, response
    if response.status_code != 200:
        # Name the endpoint and the status only: never the credential, never the issued secret.
        return None, ConfinementError("auth_failed", f"{label} at {path} answered {response.status_code}",
                                      status_code=response.status_code, duration_ms=response.duration_ms)
    if cookie:
        issued = _cookie_pair(response.headers.get("set-cookie"))
        if issued is None:
            return None, ConfinementError("auth_failed", f"login at {path} returned no session cookie",
                                          status_code=response.status_code, duration_ms=response.duration_ms)
        return issued, None
    issued = _token_value(response.body, auth.token_field)
    if issued is None:
        # The body is not echoed: it carries the token itself.
        return None, ConfinementError("auth_failed", f"token at {path} returned no {auth.token_field}",
                                      status_code=response.status_code, duration_ms=response.duration_ms)
    return issued, None


def _token_value(body: bytes, field: str) -> str | None:
    """The token out of a token endpoint's JSON answer, or None. The body itself is never kept."""
    try:
        payload = json.loads(bytes(body or b"").decode("utf-8"))
    except (ValueError, UnicodeDecodeError, AttributeError):
        return None
    token = payload.get(field) if isinstance(payload, dict) else None
    return _holdable(token) if isinstance(token, str) else None


def perform(deadline: Deadline, method: str, url: str, *, headers: dict[str, str], content: bytes | None,
            extensions: dict[str, Any], verify: bool, limit: int) -> RawResponse | ConfinementError:
    """One HTTP exchange under ``deadline``. Shared with the dev sender; does no address vetting."""
    started = deadline.started
    headers = {**headers, "Accept-Encoding": "identity"}
    try:
        transport = _WatchedTransport(deadline, verify=verify)
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=make_timeout(deadline.budget),
                          transport=transport) as client:
            try:
                with client.stream(method, url, headers=headers, content=content, extensions=extensions) as resp:
                    try:
                        status = resp.status_code
                        if 300 <= status < 400:
                            return ConfinementError("redirect_refused", "provider answered with a redirect",
                                                    status_code=status, duration_ms=_ms(started))
                        data = read_body(resp, deadline, limit)
                        if isinstance(data, ConfinementError):
                            return data
                        out_headers = {k.lower(): v for k, v in resp.headers.items()}
                    finally:
                        deadline.disarm()
            finally:
                deadline.disarm()
    except httpx.TimeoutException:
        return ConfinementError("timeout", "no answer in time", duration_ms=_ms(started))
    except httpx.HTTPError as exc:
        if deadline.expired.is_set():
            return ConfinementError("timeout", "total time budget exceeded", duration_ms=_ms(started))
        return ConfinementError("connection", f"transport failed: {type(exc).__name__}", duration_ms=_ms(started))
    return RawResponse(status_code=status, headers=out_headers, body=data, duration_ms=_ms(started) or 0)


def make_timeout(budget: float) -> httpx.Timeout:
    """Phase timeouts that add up to about one budget before the first byte (connect + wait)."""
    connect = min(budget / 2, 5.0)
    return httpx.Timeout(connect=connect, read=max(budget - connect, 0.05), write=max(budget / 4, 0.05), pool=budget)


def read_body(resp: httpx.Response, deadline: Deadline, limit: int) -> bytes | ConfinementError:
    """Stream the RAW body under the call's deadline and the size cap.

    Raw bytes are counted (never decompressed), so a compression bomb cannot expand past the cap;
    an encoded response is refused. The deadline's watchdog unblocks a stalled read.
    """
    started, status = deadline.started, resp.status_code
    encoding = resp.headers.get("content-encoding", "identity").strip().lower()
    if encoding not in ("", "identity"):
        return ConfinementError("malformed", "provider sent an encoded body (identity was requested)",
                                status_code=status, duration_ms=_ms(started))
    declared = resp.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        return ConfinementError("too_large", "response larger than max_bytes", status_code=status, duration_ms=_ms(started))
    if deadline.remaining() <= 0 or deadline.expired.is_set():
        return ConfinementError("timeout", "total time budget exceeded", status_code=status, duration_ms=_ms(started))
    chunks: list[bytes] = []
    size = 0
    try:
        for chunk in resp.iter_raw():
            size += len(chunk)
            if size > limit:
                return ConfinementError("too_large", "response larger than max_bytes", status_code=status, duration_ms=_ms(started))
            chunks.append(chunk)
            if deadline.expired.is_set() or deadline.remaining() <= 0:
                return ConfinementError("timeout", "total time budget exceeded", status_code=status, duration_ms=_ms(started))
    except httpx.HTTPError:
        if deadline.expired.is_set():
            return ConfinementError("timeout", "total time budget exceeded", status_code=status, duration_ms=_ms(started))
        raise
    if deadline.expired.is_set():
        return ConfinementError("timeout", "total time budget exceeded", status_code=status, duration_ms=_ms(started))
    return b"".join(chunks)


def _nondefault(scheme: str, port: int) -> bool:
    return (scheme == "http" and port != 80) or (scheme == "https" and port != 443)
