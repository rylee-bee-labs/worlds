"""Reference provider: an in-process HTTP server plus a TEST-ONLY sender.

Contract: docs/rebuild/CONTRACTS.md (C1 providers, C2 ``error_class``).

``ReferenceServer`` is a stdlib :class:`~http.server.ThreadingHTTPServer` bound to
127.0.0.1 on an ephemeral port, serving in a daemon thread. It speaks a small,
deliberately awkward HTTP dialect so the runner's failure paths can be exercised
for real instead of mocked:

* happy JSON (``/items``, ``/status``, ``/empty``, ``/echo-query``),
* a stateful POST that counts (``/actions/ping``, ``/lost``),
* the whole ``error_class`` surface (``/slow``, ``/boom``, ``/validate``,
  ``/malformed``, ``/redirect``, ``/oversize``, ``/secret``),
* credential shapes (``/echo-auth``, ``/secret-echo``),
* a cookie-session login (``/api/v2/auth/login`` issuing ``Set-Cookie``) and its protected reads
  (``/cookie-protected``, ``/cookie-denied``, ``/actions/cookie-denied``),
* a password-grant token endpoint (``/api/v2/auth/token`` issuing a bearer token) and its
  protected reads (``/bearer-protected``, ``/bearer-denied``).

``reference_send`` is **test-only**. It is *not* the confinement module and it is
*not* the production outbound path: it makes no SSRF, DNS, redirect or
credential-store decision beyond what these acceptance tests need. Production
outbound traffic goes through
:func:`personal_world.worlds.confinement.confined_request`, which refuses to send
until L-authority replaces the stub. What ``reference_send`` does guarantee is
the *shape* the runner may rely on: exactly one network attempt, redirects never
followed, a byte ceiling enforced while streaming, and the C2 ``error_class``
vocabulary -- and never a secret value in a note.
"""

from __future__ import annotations

import base64
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Iterable, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit

from .confinement import ConfinementError, Deadline, RawResponse, perform
from .models import Provider, Request

__all__ = ["ReferenceServer", "reference_send"]

ITEMS: dict[str, Any] = {
    "items": [
        {"id": 1, "name": "alpha", "size": 1024},
        {"id": 2, "name": "beta", "size": 2048},
    ],
    "total": 2,
}
STATUS: dict[str, Any] = {
    "state": "ok",
    "uptime": 3725,
    "cpu": 0.256,
    "disk": {"used": 512, "total": 1024},
}
EMPTY: dict[str, Any] = {"items": []}
OVERSIZE_BYTES = 3 * 1024 * 1024


def _encode(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload).encode()


class _Server(ThreadingHTTPServer):
    """Threading server that knows the :class:`ReferenceServer` that owns it."""

    daemon_threads = True
    owner: "ReferenceServer"

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Stay quiet: a client hanging up mid-answer is one of the tests."""


class _Handler(BaseHTTPRequestHandler):
    """Routes one request on the reference server. Owner is the ReferenceServer."""

    server_version = "pw-reference/1.0"
    protocol_version = "HTTP/1.0"  # one request per connection; no keep-alive state

    # -- plumbing ---------------------------------------------------------

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003 - stdlib name
        """Silence stderr: the reference server must not pollute test output."""

    @property
    def _owner(self) -> "ReferenceServer":
        return self.server.owner  # type: ignore[attr-defined]

    def _record(self) -> tuple[str, str]:
        split = urlsplit(self.path)
        self._owner.record(self.command, split.path, dict(self.headers))
        return split.path, split.query

    def _read_body(self) -> bytes:
        """The request body, when the client declared one. Login forms are the only bodies read."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return b""
        return self.rfile.read(length) if length > 0 else b""

    def _cookie_read(self) -> None:
        """A read that only answers while the request carries a live session cookie."""
        owner = self._owner
        token = ""  # nosec B105  # an empty starting value, not a credential
        for part in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == owner.cookie_name:
                token = value
        with owner._lock:
            live = token in owner.sessions
        if live:
            self._json(200, {"ok": True, "items": [1, 2]})
        else:
            self._json(403, {"error": "forbidden"})

    def _cookie_login(self, body: bytes) -> None:
        """Issue a session cookie for good credentials, 403 for bad ones. Never logs the value."""
        owner = self._owner
        if owner.username is None or owner.password is None:
            self._json(404, {"error": "not_found"})
            return
        form = dict(parse_qsl(body.decode("utf-8", "replace"), keep_blank_values=True))
        if form.get("username") != owner.username or form.get("password") != owner.password:
            self._json(403, {"error": "bad_credentials"})
            return
        cookie = f"{owner.cookie_name}={secrets.token_urlsafe(16)}"
        with owner._lock:
            owner.sessions.add(cookie.partition("=")[2])
            owner.issued_cookies.append(cookie)
        self._json(200, {"status": "ok"}, {"Set-Cookie": f"{cookie}; HttpOnly; Path=/"})

    def _grant_token(self, body: bytes) -> None:
        """Issue a bearer token for good credentials, 403 for bad ones. Never logs the value."""
        owner = self._owner
        if owner.username is None or owner.password is None:
            self._json(404, {"error": "not_found"})
            return
        form = dict(parse_qsl(body.decode("utf-8", "replace"), keep_blank_values=True))
        if form.get("username") != owner.username or form.get("password") != owner.password:
            self._json(403, {"error": "bad_credentials"})
            return
        token = secrets.token_urlsafe(24)
        with owner._lock:
            owner.valid_tokens.add(token)
            owner.issued_tokens.append(token)
        self._json(200, {"access_token": token, "token_type": "Bearer"})  # nosec B105  # "Bearer" is the OAuth token type, not a credential

    def _bearer_read(self) -> None:
        """A read that only answers while the request carries a bearer token this server issued."""
        if self._bearer_authorized():
            self._json(200, {"ok": True, "items": [1, 2]})
        else:
            self._json(401, {"error": "unauthorized"})

    def _bearer_authorized(self) -> bool:
        """True only for ``Authorization: Bearer <a token this server issued>`` (memory only)."""
        header = self.headers.get("Authorization") or ""
        if not header.startswith("Bearer "):
            return False
        token = header[len("Bearer "):]
        with self._owner._lock:
            return bool(token) and token in self._owner.valid_tokens

    def _json(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode()
        self._respond(status, body, "application/json", headers)

    def _respond(
        self,
        status: int,
        body: bytes,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
    ) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            # The client hung up early (timeout, size ceiling, lost response).
            # That is the point of those tests, not a server fault.
            self.close_connection = True

    def _authorized(self) -> bool:
        expected = self._owner.token
        received = self.headers.get("Authorization")
        if expected is None:
            return True  # no token configured: the endpoints stay open
        return received == f"Bearer {expected}"

    def _drop(self) -> None:
        """Take effect, then close the socket without answering at all."""
        self.close_connection = True
        try:
            self.connection.close()
        except OSError:
            pass

    # -- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        path, query = self._record()
        if path == "/items":
            self._json(200, ITEMS)
        elif path == "/status":
            self._json(200, STATUS)
        elif path == "/empty":
            self._json(200, EMPTY)
        elif path == "/echo-query":
            self._json(200, dict(parse_qsl(query, keep_blank_values=True)))
        elif path == "/slow":
            time.sleep(float(dict(parse_qsl(query)).get("delay", "1")))
            self._json(200, {"slept": True})
        elif path == "/stall":
            # Headers and one chunk, then silence: one blocked read must not outlive the deadline.
            try:
                self.send_response(200)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(b"1\r\nz\r\n")
                self.wfile.flush()
                time.sleep(float(dict(parse_qsl(query)).get("delay", "5")))
            except OSError:
                self.close_connection = True
        elif path == "/boom":
            self._json(500, {"error": "boom"})
        elif path == "/malformed":
            self._respond(200, b"not json {", "application/json")
        elif path == "/redirect":
            self._respond(302, b"", "application/json", {"Location": "/items"})
        elif path == "/oversize":
            self._respond(200, b"x" * OVERSIZE_BYTES, "application/octet-stream")
        elif path == "/secret":
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
            else:
                self._json(200, {"ok": True})
        elif path == "/secret-echo":
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
            else:
                self._json(200, {"authorization": self.headers.get("Authorization")})
        elif path == "/echo-auth":
            self._json(
                200,
                {
                    "authorization": self.headers.get("Authorization"),
                    "x-api-key": self.headers.get("X-Api-Key"),
                },
            )
        elif path == "/cookie-protected":
            self._cookie_read()
        elif path == "/cookie-denied":
            # Always refuses, so the caller's one re-login and one retry can be observed.
            self._json(403, {"error": "forbidden"})
        elif path == "/bearer-protected":
            self._bearer_read()
        elif path == "/bearer-denied":
            # Always refuses, so the caller's one re-token and one retry can be observed.
            self._json(401, {"error": "unauthorized"})
        else:
            self._json(404, {"error": "not_found"})

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib name
        self._record()
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        path, _ = self._record()
        if path == "/api/v2/auth/login":
            body = self._read_body()
            self._owner.record_body(path, body)
            self._cookie_login(body)
        elif path == "/api/v2/auth/token":
            body = self._read_body()
            self._owner.record_body(path, body)
            self._grant_token(body)
        elif path == "/actions/ping":
            key = self.headers.get("Idempotency-Key")
            replay = self._owner.replay(key) if key else None
            if replay is None:
                replay = _encode({"ok": True, "count": self._owner.bump("ping")})
                if key:
                    self._owner.remember(key, replay)
            self._respond(200, replay)
        elif path == "/actions/cookie-denied":
            # Always refuses, so the sender's "a write is never replayed" rule can be observed.
            self._owner.bump("cookie-denied")
            self._json(403, {"error": "forbidden"})
        elif path == "/actions/bearer-denied":
            # Always refuses, likewise for a token.
            self._owner.bump("bearer-denied")
            self._json(401, {"error": "unauthorized"})
        elif path == "/validate":
            self._json(422, {"error": "validation_failed"})
        elif path == "/lost":
            self._owner.bump("lost")  # the effect really happens ...
            self._drop()  # ... but the answer never does
        else:
            self._json(404, {"error": "not_found"})


# Ports of reference servers that are running right now: the dev sender talks to these and no others.
_LIVE_PORTS: set[int] = set()


class ReferenceServer:
    """A loopback HTTP server with the endpoints the acceptance tests need.

    ``with ReferenceServer(token="s3cret-value") as srv:`` starts a daemon thread
    and, on exit, shuts the server down and closes the listening socket (so a
    later connect to the same port is refused -- that is how the ``connection``
    case is provoked).
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        username: str | None = None,
        password: str | None = None,
        cookie_name: str = "SID",
    ) -> None:
        self.token = token
        # When both are set, /api/v2/auth/login accepts them and issues a session cookie.
        self.username = username
        self.password = password
        self.cookie_name = cookie_name
        self.counters: dict[str, int] = {}
        self.calls: list[tuple[str, str, dict[str, str]]] = []
        # Bodies of POSTs the harness needs to inspect (login form), never sent anywhere else.
        self.post_bodies: list[tuple[str, bytes]] = []
        self.sessions: set[str] = set()
        self.issued_cookies: list[str] = []
        # Bearer tokens issued by /api/v2/auth/token. Memory only, for the life of the server.
        self.valid_tokens: set[str] = set()
        self.issued_tokens: list[str] = []
        self._idempotent: dict[str, bytes] = {}
        self._lock = threading.Lock()
        self._httpd = _Server(("127.0.0.1", 0), _Handler)
        self._httpd.owner = self
        self._thread: threading.Thread | None = None
        host, port = self._httpd.server_address[:2]
        self.port = port
        self.base_url = f"http://{host}:{port}"

    # -- lifecycle --------------------------------------------------------

    def start(self) -> "ReferenceServer":
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        _LIVE_PORTS.add(self.port)
        return self

    def stop(self) -> None:
        _LIVE_PORTS.discard(self.port)
        self._httpd.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._httpd.server_close()

    def __enter__(self) -> "ReferenceServer":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- observability ----------------------------------------------------

    def calls_to(self, path: str) -> int:
        """How many requests reached ``path`` (query string not counted)."""
        return sum(1 for _, seen, _ in self.calls if seen == path)

    def expire_sessions(self) -> None:
        """Forget every live session, so the next protected read must re-login."""
        with self._lock:
            self.sessions.clear()

    def rotate_tokens(self) -> None:
        """Forget every issued bearer token, so the next protected read must re-token."""
        with self._lock:
            self.valid_tokens.clear()

    def record_body(self, path: str, body: bytes) -> None:
        with self._lock:
            self.post_bodies.append((path, body))

    def bodies_to(self, path: str) -> list[bytes]:
        """The bodies of POSTs that reached ``path`` (test harness only; never a credential store)."""
        with self._lock:
            return [body for seen, body in self.post_bodies if seen == path]

    def issued_cookie(self) -> str | None:
        """The last ``name=value`` cookie this server issued, or None. Test harness only."""
        with self._lock:
            return self.issued_cookies[-1] if self.issued_cookies else None

    def issued_token(self) -> str | None:
        """The last bearer token this server issued, or None. Test harness only."""
        with self._lock:
            return self.issued_tokens[-1] if self.issued_tokens else None

    # -- counters (called from handler threads) ---------------------------

    def bump(self, name: str) -> int:
        with self._lock:
            self.counters[name] = self.counters.get(name, 0) + 1
            return self.counters[name]

    def remember(self, key: str, body: bytes) -> None:
        with self._lock:
            self._idempotent[key] = body

    def replay(self, key: str) -> bytes | None:
        with self._lock:
            return self._idempotent.get(key)

    def record(self, method: str, path: str, headers: dict[str, str]) -> None:
        with self._lock:
            self.calls.append((method, path, headers))


Sender = Callable[[Provider, Request], RawResponse | ConfinementError]


def _build_url(provider: Provider, request: Request) -> str:
    base = provider.base_url.rstrip("/")
    prefix = provider.path_prefix.rstrip("/")
    return f"{base}{prefix}{request.path}"


def _secret_name(ref: str | None) -> str:
    """The NAME after ``env:``/``vault:`` (a validated ref), never a value."""
    return (ref or "").partition(":")[2]


def _cookie_pair(set_cookie: str | None) -> str | None:
    """The ``name=value`` of a Set-Cookie header; its attributes never travel back."""
    if not set_cookie:
        return None
    pair = set_cookie.split(";", 1)[0].strip()
    return pair or None


def _auth_headers(auth: Any, secrets: dict[str, str]) -> tuple[dict[str, str] | None, str | None]:
    """Headers to add for ``auth``, or ``(None, note)`` when the secret is missing.

    The note never contains a secret value -- only the name of what was missing.
    ``cookie_session`` is handled by the sender's session path; it never becomes a header here.
    """
    if auth.type == "none" or not auth.secret_ref:
        return {}, None
    value = secrets.get(_secret_name(auth.secret_ref))
    if value is None:
        return None, f"secret not available for {auth.secret_ref}"
    if auth.type == "bearer":
        return {"Authorization": f"Bearer {value}"}, None
    if auth.type == "header":
        return {auth.header_name or "X-Api-Key": value}, None
    if auth.type == "basic":
        encoded = base64.b64encode(value.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}, None
    return None, f"unsupported auth type {auth.type}"


def reference_send(secrets: dict[str, str], *, allowed_ports: Iterable[int] | None = None) -> Sender:
    """Build the TEST-ONLY sender used by the reference-provider tests.

    TEST ONLY. This is **not** the confinement module and not the production
    outbound path -- see the module docstring. It performs exactly one attempt
    per call, never follows a redirect, enforces ``provider.max_bytes`` while
    streaming, maps transport failures onto the C2 ``error_class`` vocabulary,
    and never puts a secret value into a note.

    For ``auth.type cookie_session`` the session cookie lives only in this closure's memory:
    it is never logged, persisted, cached, noted or returned. A process restart simply
    logs in again. A ``403`` on a READ triggers one re-login and one replay of that request; a
    WRITE is never replayed (it is returned as the refusal it is, and the stale session is dropped
    so the next call logs in fresh). A second refusal of a read is reported, never swallowed and
    never looped. Same rule for ``auth.type password_grant`` and its bearer token: a ``401`` on a
    read re-tokens once and replays once, on a write it does not.

    Returns ``RawResponse`` for any completed exchange -- including 4xx/5xx and
    undecodable bodies: whether a status is a failure is the runner's call.
    """

    #: provider identity -> ``name=value`` session cookie. In memory only, for the life of this closure.
    sessions: dict[tuple[str, ...], str] = {}
    session_lock = threading.Lock()
    #: provider identity -> bearer token. In memory only, for the life of this closure.
    tokens: dict[tuple[str, ...], str] = {}
    token_lock = threading.Lock()

    def send(provider: Provider, request: Request, *, effect: Literal["read", "write"],
             in_scope: bool = True) -> RawResponse | ConfinementError:
        started = time.monotonic()

        def elapsed_ms() -> int:
            return int((time.monotonic() - started) * 1000)

        if not in_scope:  # the call site's scope verdict, before any socket (login and token fetches included)
            return ConfinementError("auth_failed", "capability is outside the credential's scope",
                                    duration_ms=elapsed_ms(), pre_send=True)

        parts = urlsplit(provider.base_url)
        try:
            port = parts.port
        except ValueError:
            port = None
        permitted = set(allowed_ports) if allowed_ports is not None else _LIVE_PORTS
        if provider.kind != "reference" or parts.hostname != "127.0.0.1" or port not in permitted:
            return ConfinementError(
                "confinement_denied",
                "reference sender only serves kind=reference at 127.0.0.1 on a running reference server's port",
                duration_ms=elapsed_ms(),
            )

        if provider.auth.type == "cookie_session":
            return _session_send(provider, request, effect)
        if provider.auth.type == "password_grant":
            return _grant_send(provider, request, effect)

        headers: dict[str, str] = dict(request.headers)
        auth_headers, missing = _auth_headers(provider.auth, secrets)
        if auth_headers is None:
            # Nothing is sent at all: an unreachable credential fails closed.
            return ConfinementError("auth_failed", missing or "", duration_ms=elapsed_ms())
        headers.update(auth_headers)

        timeout_s = request.timeout_s or provider.timeout_s
        deadline = Deadline(timeout_s)
        try:
            url = _build_url(provider, request)
            if request.query:
                url += "?" + urlencode(request.query)
            content = json.dumps(request.body).encode() if request.body is not None else None
            if content is not None:
                headers.setdefault("Content-Type", "application/json")
            return perform(deadline, request.method, url, headers=headers, content=content, extensions={},
                           verify=False, limit=provider.max_bytes)
        finally:
            deadline.disarm()

    def _exchange(method: str, url: str, headers: dict[str, str], content: bytes | None,
                  timeout_s: float, max_bytes: int) -> RawResponse | ConfinementError:
        """One exchange with its own budget; the cookie never enters a header dict outside the caller."""
        deadline = Deadline(timeout_s)
        try:
            return perform(deadline, method, url, headers=headers, content=content, extensions={},
                           verify=False, limit=max_bytes)
        finally:
            deadline.disarm()

    def _login(provider: Provider, request: Request) -> tuple[str | None, ConfinementError | None]:
        """POST the credential, return the session cookie pair, or the failure. Flow only."""
        auth = provider.auth
        credential = secrets.get(_secret_name(auth.secret_ref))
        if credential is None:
            return None, ConfinementError("auth_failed", f"secret not available for {auth.secret_ref}")
        username, sep, password = credential.partition(":")
        if not sep:
            # The pair travels as one secret (like basic); the note names the ref, never the value.
            return None, ConfinementError(
                "auth_failed", f"credential for {auth.secret_ref} must be username:password")
        body = urlencode({auth.username_field: username, auth.password_field: password}).encode()
        url = f"{provider.base_url.rstrip('/')}{provider.path_prefix.rstrip('/')}{auth.login_path}"
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
        response = _exchange("POST", url, headers, body,
                             request.timeout_s or provider.timeout_s, provider.max_bytes)
        if isinstance(response, ConfinementError):
            return None, response
        if response.status_code != 200:
            # Name the endpoint and status only: never the credential, never a Set-Cookie value.
            return None, ConfinementError(
                "auth_failed", f"login at {auth.login_path} answered {response.status_code}",
                status_code=response.status_code)
        cookie = _cookie_pair(response.headers.get("set-cookie"))
        if cookie is None:
            return None, ConfinementError(
                "auth_failed", f"login at {auth.login_path} returned no session cookie",
                status_code=response.status_code)
        return cookie, None

    def _session_read(provider: Provider, request: Request, cookie: str) -> RawResponse | ConfinementError:
        headers = dict(request.headers)
        headers["Cookie"] = cookie  # attached from memory; request.headers never carries a cookie
        url = _build_url(provider, request)
        if request.query:
            url += "?" + urlencode(request.query)
        content = json.dumps(request.body).encode() if request.body is not None else None
        if content is not None:
            headers.setdefault("Content-Type", "application/json")
        return _exchange(request.method, url, headers, content,
                         request.timeout_s or provider.timeout_s, provider.max_bytes)

    def _session_send(provider: Provider, request: Request, effect: str) -> RawResponse | ConfinementError:
        key = (
            provider.id, provider.base_url, provider.path_prefix,
            provider.auth.login_path or "", provider.auth.secret_ref or "",
        )
        with session_lock:
            cookie = sessions.get(key)
        if cookie is None:
            cookie, error = _login(provider, request)
            if error is not None:
                return error
            with session_lock:
                sessions[key] = cookie
        response = _session_read(provider, request, cookie)
        if isinstance(response, RawResponse) and response.status_code == 403:
            # The session was refused. It is stale either way, so it goes; a WRITE is never
            # replayed (ADR-0008: no automatic side-effect retries), a read gets one re-login.
            with session_lock:
                sessions.pop(key, None)
            if effect != "read":
                return response
            cookie, error = _login(provider, request)
            if error is not None:
                return error  # a failed re-login is a failure, never a swallowed success
            with session_lock:
                sessions[key] = cookie
            response = _session_read(provider, request, cookie)
            if isinstance(response, RawResponse) and response.status_code == 403:
                return ConfinementError(
                    "auth_failed", f"session refused at {provider.auth.login_path}",
                    status_code=response.status_code, duration_ms=response.duration_ms)
        return response

    def _fetch_token(provider: Provider, request: Request) -> tuple[str | None, ConfinementError | None]:
        """POST the credential, return the bearer token, or the failure. Flow only."""
        auth = provider.auth
        credential = secrets.get(_secret_name(auth.secret_ref))
        if credential is None:
            return None, ConfinementError("auth_failed", f"secret not available for {auth.secret_ref}")
        username, sep, password = credential.partition(":")
        if not sep:
            # The pair travels as one secret (like basic/cookie_session); the note names the ref, never the value.
            return None, ConfinementError(
                "auth_failed", f"credential for {auth.secret_ref} must be username:password")
        body = urlencode({auth.username_field: username, auth.password_field: password}).encode()
        url = f"{provider.base_url.rstrip('/')}{provider.path_prefix.rstrip('/')}{auth.token_path}"
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
        response = _exchange("POST", url, headers, body,
                             request.timeout_s or provider.timeout_s, provider.max_bytes)
        if isinstance(response, ConfinementError):
            return None, response
        if response.status_code != 200:
            # Name the endpoint and status only: never the credential, never the token.
            return None, ConfinementError(
                "auth_failed", f"token at {auth.token_path} answered {response.status_code}",
                status_code=response.status_code)
        try:
            payload = json.loads(bytes(response.body or b"").decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = None
        token = payload.get(auth.token_field) if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            # The body is not echoed: it may carry the token itself.
            return None, ConfinementError(
                "auth_failed", f"token at {auth.token_path} returned no {auth.token_field}",
                status_code=response.status_code)
        return token, None

    def _grant_read(provider: Provider, request: Request, token: str) -> RawResponse | ConfinementError:
        headers = dict(request.headers)
        headers["Authorization"] = f"Bearer {token}"  # attached from memory; request.headers never carries it
        url = _build_url(provider, request)
        if request.query:
            url += "?" + urlencode(request.query)
        content = json.dumps(request.body).encode() if request.body is not None else None
        if content is not None:
            headers.setdefault("Content-Type", "application/json")
        return _exchange(request.method, url, headers, content,
                         request.timeout_s or provider.timeout_s, provider.max_bytes)

    def _grant_send(provider: Provider, request: Request, effect: str) -> RawResponse | ConfinementError:
        key = (
            provider.id, provider.base_url, provider.path_prefix,
            provider.auth.token_path or "", provider.auth.secret_ref or "",
        )
        with token_lock:
            token = tokens.get(key)
        if token is None:
            token, error = _fetch_token(provider, request)
            if error is not None:
                return error
            with token_lock:
                tokens[key] = token
        response = _grant_read(provider, request, token)
        if isinstance(response, RawResponse) and response.status_code == 401:
            # The token was refused. It is stale either way, so it goes; a WRITE is never replayed
            # (ADR-0008: no automatic side-effect retries), a read gets one re-token and one replay.
            with token_lock:
                tokens.pop(key, None)
            if effect != "read":
                return response
            token, error = _fetch_token(provider, request)
            if error is not None:
                return error  # a failed re-token is a failure, never a swallowed success
            with token_lock:
                tokens[key] = token
            response = _grant_read(provider, request, token)
            if isinstance(response, RawResponse) and response.status_code == 401:
                return ConfinementError(
                    "auth_failed", f"token at {provider.auth.token_path} was refused",
                    status_code=response.status_code, duration_ms=response.duration_ms)
        return response

    return send
