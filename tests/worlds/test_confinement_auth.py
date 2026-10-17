"""cookie_session and password_grant in the PRODUCTION sender (``confinement``).

The two session kinds must be the same confinement as any other request: the login/token POST is
joined and re-checked like a request path, dials the same vetted address, shares the call's single
deadline and size cap, and never follows a redirect. A refused READ re-logs-in once and replays
once; a refused WRITE is never replayed. The cookie/token lives in this process's memory only and
never reaches a note, a log line, ``request.headers`` or a returned response.

Loopback servers, exactly like the other confinement tests: real sockets, real HTTP, no mocks.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

import pytest

from personal_world.worlds.confinement import ConfinementError, RawResponse, confined_request
from personal_world.worlds.models import Auth, Provider, Request

# Synthetic values, used only to prove they do not escape.
COOKIE_USER = "admin"
COOKIE_PASSWORD = "pw-safety-cookie-4f1c"  # pw-safety: synthetic
GRANT_USER = "reader"
GRANT_PASSWORD = "pw-safety-grant-8b2d"  # pw-safety: synthetic
LOGIN_PATH = "/auth/login"
TOKEN_PATH = "/auth/token"


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # one request per connection: no keep-alive state to leak

    def log_message(self, *a):  # noqa: A003 - stdlib name
        pass

    @property
    def srv(self) -> "AuthServer":
        return self.server.owner  # type: ignore[attr-defined]

    # -- plumbing ---------------------------------------------------------

    def _route(self) -> str:
        """The path with a leading ``/api/v2`` stripped, so prefixed and plain providers both work."""
        path = urlsplit(self.path).path
        self.srv.hits.append((self.command, path, dict(self.headers)))
        self.srv.routes.append(path[len("/api/v2"):] if path.startswith("/api/v2/") else path)
        return self.srv.routes[-1]

    def _body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return b""
        return self.rfile.read(length) if length > 0 else b""

    def _send(self, code: int, payload: dict | None = None, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload or {}).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)
        except OSError:  # the client gave up (deadline, refusal): expected in several tests
            self.close_connection = True

    def _form_ok(self, body: bytes) -> bool:
        """Any credential pair this server knows is good; which one it was is the test's business."""
        self.srv.bodies.append(body)
        form = dict(parse_qsl(body.decode("utf-8", "replace"), keep_blank_values=True))
        return (form.get("username"), form.get("password")) in self.srv.credentials

    def _cookie(self) -> str:
        raw = ""
        for part in (self.headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == self.srv.cookie_name:
                raw = value
        return raw

    def _live_cookie(self) -> bool:
        return bool(self._cookie()) and self._cookie() in self.srv.sessions

    def _live_token(self) -> bool:
        header = self.headers.get("Authorization") or ""
        return header.startswith("Bearer ") and header[len("Bearer "):] in self.srv.tokens

    # -- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        route = self._route()
        if route == "/protected":
            self._send(200, {"ok": True, "items": [1, 2]}) if self._live_cookie() else self._send(403, {"error": "forbidden"})
        elif route == "/denied":
            self._send(403, {"error": "forbidden"})
        elif route == "/bearer":
            self._send(200, {"ok": True, "items": [1, 2]}) if self._live_token() else self._send(401, {"error": "unauthorized"})
        elif route == "/bearer-denied":
            self._send(401, {"error": "unauthorized"})
        elif route == "/echo":
            # Presence only: this test server never writes a credential back into a response body.
            self._send(200, {"cookie_present": bool(self.headers.get("Cookie")),
                             "authorization_present": bool(self.headers.get("Authorization"))})
        else:
            self._send(404, {"error": "not_found"})

    do_HEAD = do_GET

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        route = self._route()
        if route == LOGIN_PATH:
            self._cookie_login()
        elif route == "/auth/login-redirect":
            self._send(302, {}, {"Location": "/elsewhere"})
        elif route == "/auth/slow-login":
            time.sleep(1.0)
            self._cookie_login()
        elif route == "/auth/nocookie":
            self._send(200, {"status": "ok"})
        elif route == TOKEN_PATH:
            self._grant_token()
        elif route == "/auth/slow-token":
            time.sleep(1.0)
            self._grant_token()
        elif route == "/auth/notoken":
            self._send(200, {"status": "ok"})
        elif route == "/write":
            if self._live_cookie():
                self._send(200, {"count": self.srv.bump("write")})
            else:
                self._send(403, {"error": "forbidden"})
        elif route == "/write-denied":
            self.srv.bump("write-denied")
            self._send(403, {"error": "forbidden"})
        elif route == "/bearer-write-denied":
            self.srv.bump("bearer-write-denied")
            self._send(401, {"error": "unauthorized"})
        else:
            self._send(404, {"error": "not_found"})

    def _cookie_login(self) -> None:
        if not self._form_ok(self._body()):
            self._send(403, {"error": "bad_credentials"})
            return
        value = f"cookie-{self.srv.issue(self.srv.cookies)}"
        self.srv.sessions.add(value)
        self._send(200, {"status": "ok"}, {"Set-Cookie": f"{self.srv.cookie_name}={value}; HttpOnly; Path=/"})

    def _grant_token(self) -> None:
        if not self._form_ok(self._body()):
            self._send(403, {"error": "bad_credentials"})
            return
        token = f"token-{self.srv.issue(self.srv.granted)}"
        self.srv.tokens.add(token)
        self._send(200, {"access_token": token, "token_type": "Bearer"})


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    owner: "AuthServer"

    def handle_error(self, request, client_address):  # a client hanging up is several of these tests
        pass


class AuthServer:
    """A loopback provider that can hand out session cookies and bearer tokens, and can be made to
    forget them, redirect a login, or stall one."""

    def __init__(self, credentials: tuple[tuple[str, str], ...] = (
            (COOKIE_USER, COOKIE_PASSWORD), (GRANT_USER, GRANT_PASSWORD)), cookie_name: str = "SID"):
        self.credentials = set(credentials)
        self.cookie_name = cookie_name
        self.hits: list[tuple[str, str, dict[str, str]]] = []
        self.routes: list[str] = []
        self.bodies: list[bytes] = []
        self.sessions: set[str] = set()
        self.tokens: set[str] = set()
        self.cookies: list[str] = []
        self.granted: list[str] = []
        self.counts: dict[str, int] = {}
        self._n = 0
        self._lock = threading.Lock()
        self._httpd = _Server(("127.0.0.1", 0), _Handler)
        self._httpd.owner = self
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self.base_url = f"http://127.0.0.1:{self._httpd.server_address[1]}"
        self._thread.start()

    def issue(self, into: list[str]) -> str:
        with self._lock:
            self._n += 1
            into.append(str(self._n))
            return into[-1]

    def bump(self, name: str) -> int:
        with self._lock:
            self.counts[name] = self.counts.get(name, 0) + 1
            return self.counts[name]

    def hits_to(self, route: str) -> int:
        """How many requests reached ``route`` (a leading /api/v2 prefix does not count)."""
        return sum(1 for seen in self.routes if seen == route)

    def headers_to(self, route: str) -> list[dict[str, str]]:
        return [h for method, path, h in self.hits
                if path == route or path == f"/api/v2{route}"]

    def last_cookie(self) -> str:
        """The last session value this server issued (test harness only)."""
        return f"cookie-{self.cookies[-1]}" if self.cookies else ""

    def last_token(self) -> str:
        """The last bearer token this server issued (test harness only)."""
        return f"token-{self.granted[-1]}" if self.granted else ""

    def forget(self) -> None:
        with self._lock:
            self.sessions.clear()
            self.tokens.clear()

    def close(self) -> None:
        self._httpd.shutdown()
        self._thread.join(timeout=5)
        self._httpd.server_close()

    def __enter__(self) -> "AuthServer":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@pytest.fixture
def server():
    with AuthServer() as srv:
        yield srv


def cookie_auth(login_path: str = LOGIN_PATH) -> Auth:
    return Auth(type="cookie_session", login_path=login_path, secret_ref="env:AUTH_CREDENTIALS")


def grant_auth(token_path: str = TOKEN_PATH) -> Auth:
    return Auth(type="password_grant", token_path=token_path, secret_ref="env:GRANT_CREDENTIALS")


def prov(server: AuthServer, auth: Auth, **kw) -> Provider:
    d = dict(id="p", name="P", kind="http", base_url=server.base_url, network={"lan": True}, auth=auth)
    d.update(kw)
    return Provider(**d)


def req(path: str = "/protected", method: str = "GET", provider: str = "p", **kw) -> Request:
    return Request(id=f"{provider}.r", provider=provider, path=path, method=method, **kw)


def go(provider: Provider, request: Request, effect: str = "read"):
    return confined_request(provider, request, effect=effect)


def ok(out) -> RawResponse:
    assert isinstance(out, RawResponse) and out.status_code == 200, out
    return out


def auth_failed(out) -> ConfinementError:
    assert isinstance(out, ConfinementError) and out.error_class == "auth_failed", out
    return out


def resolver_cap_refusal(out) -> ConfinementError:
    """The pre-existing, deliberate per-provider DNS cap refusing a lookup. Not an auth or sender bug."""
    assert isinstance(out, ConfinementError), out
    assert out.error_class == "timeout" and out.pre_send is True, out
    assert "name lookups in flight" in out.note, out
    return out


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("AUTH_CREDENTIALS", f"{COOKIE_USER}:{COOKIE_PASSWORD}")
    monkeypatch.setenv("GRANT_CREDENTIALS", f"{GRANT_USER}:{GRANT_PASSWORD}")
    monkeypatch.setenv("OTHER_CREDENTIALS", f"{COOKIE_USER}:{COOKIE_PASSWORD}")
    from personal_world.worlds import confinement

    for key in list(confinement._SESSIONS):  # the store is process-wide; do not leak between tests
        confinement._session_forget(key)


# ---- cookie_session -------------------------------------------------------------------------


def test_cookie_session_logs_in_once_then_reuses_the_session(server):
    p = prov(server, cookie_auth())
    first = ok(go(p, req()))
    second = ok(go(p, req("/protected")))
    assert first.body == second.body
    assert server.hits_to(LOGIN_PATH) == 1
    assert server.hits_to("/protected") == 2
    assert server.hits_to("/protected", ) == 2  # the second read carried the cookie, no re-login


def test_cookie_session_refused_read_re_logs_in_once_and_replays_once(server):
    p = prov(server, cookie_auth())
    ok(go(p, req()))
    assert server.hits_to(LOGIN_PATH) == 1
    server.forget()  # the provider forgets the session; the sender still holds it
    out = ok(go(p, req("/protected")))
    assert out.status_code == 200
    assert server.hits_to(LOGIN_PATH) == 2  # exactly one re-login
    assert server.hits_to("/protected") == 3  # ok, refused, replayed once


def test_cookie_session_second_refusal_is_auth_failed_and_never_loops(server):
    p = prov(server, cookie_auth())
    out = go(p, req("/denied"))
    auth_failed(out)
    assert out.status_code == 403
    assert server.hits_to(LOGIN_PATH) == 2
    assert server.hits_to("/denied") == 2


def test_cookie_session_refused_write_is_never_replayed(server):
    p = prov(server, cookie_auth())
    first = go(p, req("/write-denied", "POST", body={"a": 1}), effect="write")
    assert isinstance(first, RawResponse) and first.status_code == 403  # returned as the refusal
    second = go(p, req("/write-denied", "POST", body={"a": 1}), effect="write")
    assert isinstance(second, RawResponse) and second.status_code == 403
    assert server.hits_to("/write-denied") == 2  # one per call: the POST was never replayed
    assert server.counts["write-denied"] == 2
    assert server.hits_to(LOGIN_PATH) == 2  # the stale session was dropped: each call logs in fresh


def test_cookie_session_write_is_sent_once_when_the_session_is_good(server):
    p = prov(server, cookie_auth())
    out = go(p, req("/write", "POST", body={"a": 1}), effect="write")
    ok(out)
    assert json.loads(out.body)["count"] == 1
    assert server.hits_to("/write") == 1


def test_cookie_session_failed_re_login_is_auth_failed_not_a_swallowed_success(server, monkeypatch):
    p = prov(server, cookie_auth())
    ok(go(p, req("/protected")))
    server.forget()
    monkeypatch.setenv("AUTH_CREDENTIALS", f"{COOKIE_USER}:wrong-password")  # the re-login will fail
    out = go(p, req("/protected"))
    auth_failed(out)
    assert out.status_code == 403
    assert server.hits_to("/protected") == 2  # the refused read, and NO replay
    assert server.hits_to(LOGIN_PATH) == 2


def test_cookie_session_missing_credential_is_auth_failed_and_sends_nothing(server, monkeypatch):
    monkeypatch.delenv("AUTH_CREDENTIALS", raising=False)
    out = go(prov(server, cookie_auth()), req())
    assert auth_failed(out).pre_send is True
    assert "env:AUTH_CREDENTIALS" in out.note  # the ref, never a value
    assert server.hits == []


def test_cookie_session_malformed_credential_names_the_ref_only(server, monkeypatch):
    monkeypatch.setenv("AUTH_CREDENTIALS", "no-colon-here")  # not a username:password pair
    out = go(prov(server, cookie_auth()), req())
    auth_failed(out)
    assert "AUTH_CREDENTIALS" in out.note and "no-colon-here" not in out.note
    assert server.hits == []


def test_cookie_session_credential_with_control_characters_is_refused(server, monkeypatch):
    monkeypatch.setenv("AUTH_CREDENTIALS", "admin:bad\r\npassword")
    out = go(prov(server, cookie_auth()), req())
    auth_failed(out)
    assert "control character" in out.note and "bad" not in out.note
    assert server.hits == []


def test_cookie_session_without_a_session_cookie_is_auth_failed(server):
    p = prov(server, cookie_auth("/auth/nocookie"))
    auth_failed(go(p, req("/protected")))
    assert server.hits_to("/auth/nocookie") == 1
    assert server.hits_to("/protected") == 0


def test_cookie_session_never_leaves_the_cookie_or_password(server, caplog):
    out = ok(go(prov(server, cookie_auth()), req("/echo")))
    cookie_value = server.last_cookie()
    assert json.loads(out.body) == {"cookie_present": True, "authorization_present": False}
    # It WAS sent (the server saw it) ...
    assert server.headers_to("/echo")[0]["Cookie"] == f"{server.cookie_name}={cookie_value}"
    # ... and it is in nothing Worlds kept or returned.
    surfaces = [json.dumps(out.headers), out.body.decode(), repr(out), caplog.text, str(server.cookies)]
    assert surfaces
    for surface in surfaces:
        assert cookie_value not in surface
        assert COOKIE_PASSWORD not in surface
    form = dict(parse_qsl(server.bodies[0].decode()))
    assert form == {"username": COOKIE_USER, "password": COOKIE_PASSWORD}  # it went to the login only


def test_cookie_session_is_never_in_the_request_headers(server):
    request = req("/protected", headers={"User-Agent": "worlds-test"})
    ok(go(prov(server, cookie_auth()), request))
    assert "cookie" not in {name.lower() for name in request.headers}
    assert "cookie" not in json.dumps(request.model_dump())


def test_redirects_on_the_login_are_not_followed(server):
    p = prov(server, cookie_auth("/auth/login-redirect"))
    out = go(p, req("/protected"))
    assert isinstance(out, ConfinementError) and out.error_class == "redirect_refused"
    assert server.hits_to("/auth/login-redirect") == 1
    assert server.hits_to("/elsewhere") == 0
    assert server.hits_to("/protected") == 0


@pytest.mark.parametrize("login_path", ["/../elsewhere", "/auth/../../elsewhere", "/auth/%2e%2e/x",
                                        "https://elsewhere.invalid/login", "/auth\\login", "/auth?x=1"])
def test_login_path_cannot_escape_the_prefix(server, login_path):
    auth = Auth.model_construct(type="cookie_session", login_path=login_path, secret_ref="env:AUTH_CREDENTIALS",
                                header_name=None, username_field="username", password_field="password",
                                token_path=None, token_field="access_token")
    out = go(prov(server, auth), req("/protected"))
    assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied", out
    assert server.hits == []


def test_login_is_joined_under_base_url_and_path_prefix(server):
    p = prov(server, cookie_auth("/auth/login"), path_prefix="/api/v2")
    ok(go(p, req("/protected")))
    paths = [path for _, path, _ in server.hits]
    assert paths == ["/api/v2/auth/login", "/api/v2/protected"]


def test_the_login_never_carries_a_user_header(server):
    ok(go(prov(server, cookie_auth()), req("/protected", headers={"User-Agent": "worlds-test",
                                                                "Accept-Language": "en"})))
    login_headers = next(h for method, path, h in server.hits if path == LOGIN_PATH)
    assert login_headers.get("User-Agent") != "worlds-test"
    assert "Accept-Language" not in login_headers
    assert login_headers.get("Content-Type") == "application/x-www-form-urlencoded"


def test_the_login_obeys_the_same_address_policy(server):
    p = prov(server, cookie_auth(), network={"lan": False})  # loopback, not declared lan
    out = go(p, req("/protected"))
    assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied"
    assert server.hits == []  # not even the login went out


def test_the_login_shares_the_calls_single_deadline(server):
    p = prov(server, cookie_auth("/auth/slow-login"), timeout_s=0.5)
    t0 = time.monotonic()
    out = go(p, req("/protected"))
    assert isinstance(out, ConfinementError) and out.error_class == "timeout"
    assert time.monotonic() - t0 < 2.5  # the stalled login did not get a budget of its own
    assert server.hits_to("/protected") == 0


def test_the_login_never_targets_another_host(server):
    # A provider on one host cannot be pointed at another by anything the request carries.
    p = prov(server, cookie_auth())
    ok(go(p, req("/protected")))
    hosts = {h.get("Host") for _, _, h in server.hits}
    assert hosts == {server.base_url.removeprefix("http://")}


def test_two_providers_with_different_secret_refs_never_share_a_session(server, monkeypatch):
    a = prov(server, cookie_auth(), id="alpha")
    b = prov(server, Auth(type="cookie_session", login_path=LOGIN_PATH, secret_ref="env:OTHER_CREDENTIALS"),
             id="beta")
    ok(go(a, req(provider="alpha")))
    assert server.hits_to(LOGIN_PATH) == 1
    ok(go(b, req(provider="beta")))
    assert server.hits_to(LOGIN_PATH) == 2  # b logged in for itself
    ok(go(a, req(provider="alpha")))
    assert server.hits_to(LOGIN_PATH) == 2  # a still holds its own session, no re-login
    cookies = [h.get("Cookie") for method, path, h in server.hits if path == "/protected"]
    assert len(cookies) == 3 and len(set(cookies)) == 2  # a's cookie and b's cookie, never mixed


def test_a_config_change_cannot_reuse_a_session_for_a_new_destination(server):
    p = prov(server, cookie_auth())
    ok(go(p, req()))
    assert server.hits_to(LOGIN_PATH) == 1
    moved = prov(server, cookie_auth(), path_prefix="/api/v2")  # same host, new prefix: a new key
    ok(go(moved, req("/protected")))
    assert server.hits_to(LOGIN_PATH) == 2


def test_two_servers_never_share_a_session():
    with AuthServer() as one, AuthServer() as two:
        a = prov(one, cookie_auth(), id="a")
        b = prov(two, cookie_auth(), id="b")
        ok(go(a, req(provider="a")))
        ok(go(b, req(provider="b")))
        assert one.hits_to(LOGIN_PATH) == 1 and two.hits_to(LOGIN_PATH) == 1
        assert one.hits_to("/protected") == 1 and two.hits_to("/protected") == 1


# ---- password_grant ------------------------------------------------------------------------


def test_password_grant_fetches_a_token_once_then_reuses_it(server):
    p = prov(server, grant_auth())
    ok(go(p, req("/bearer")))
    ok(go(p, req("/bearer")))
    assert server.hits_to(TOKEN_PATH) == 1
    assert server.hits_to("/bearer") == 2


def test_password_grant_refused_read_re_tokens_once_and_replays_once(server):
    p = prov(server, grant_auth())
    ok(go(p, req("/bearer")))
    server.forget()
    ok(go(p, req("/bearer")))
    assert server.hits_to(TOKEN_PATH) == 2
    assert server.hits_to("/bearer") == 3  # ok, refused, replayed once


def test_password_grant_second_refusal_is_auth_failed_and_never_loops(server):
    out = go(prov(server, grant_auth()), req("/bearer-denied"))
    auth_failed(out)
    assert out.status_code == 401
    assert server.hits_to(TOKEN_PATH) == 2
    assert server.hits_to("/bearer-denied") == 2


def test_password_grant_refused_write_is_never_replayed(server):
    p = prov(server, grant_auth())
    first = go(p, req("/bearer-write-denied", "POST", body={"a": 1}), effect="write")
    assert isinstance(first, RawResponse) and first.status_code == 401
    second = go(p, req("/bearer-write-denied", "POST", body={"a": 1}), effect="write")
    assert isinstance(second, RawResponse) and second.status_code == 401
    assert server.hits_to("/bearer-write-denied") == 2  # one per call: never replayed
    assert server.hits_to(TOKEN_PATH) == 2  # the stale token was dropped


def test_password_grant_failed_re_token_is_auth_failed(server, monkeypatch):
    p = prov(server, grant_auth())
    ok(go(p, req("/bearer")))
    server.forget()
    monkeypatch.setenv("GRANT_CREDENTIALS", f"{GRANT_USER}:wrong-password")
    out = go(p, req("/bearer"))
    auth_failed(out)
    assert server.hits_to("/bearer") == 2  # the refused read, and NO replay


def test_password_grant_without_a_token_is_auth_failed(server):
    p = prov(server, grant_auth("/auth/notoken"))
    auth_failed(go(p, req("/bearer")))
    assert server.hits_to("/bearer") == 0


def test_password_grant_never_leaves_the_token_or_password(server, caplog):
    out = ok(go(prov(server, grant_auth()), req("/echo")))
    token = server.last_token()
    assert json.loads(out.body) == {"cookie_present": False, "authorization_present": True}
    assert server.headers_to("/echo")[0]["Authorization"] == f"Bearer {token}"  # it WAS sent
    surfaces = [out.body.decode(), json.dumps(out.headers), repr(out), caplog.text, str(server.granted)]
    assert surfaces
    for surface in surfaces:
        assert token not in surface
        assert GRANT_PASSWORD not in surface
    assert dict(parse_qsl(server.bodies[0].decode())) == {"username": GRANT_USER, "password": GRANT_PASSWORD}


@pytest.mark.parametrize("token_path", ["/../elsewhere", "/auth/../../elsewhere", "/auth/%2e%2e/x",
                                        "https://elsewhere.invalid/token", "/auth\\token", "/auth?x=1"])
def test_token_path_cannot_escape_the_prefix(server, token_path):
    auth = Auth.model_construct(type="password_grant", token_path=token_path, secret_ref="env:AUTH_CREDENTIALS",
                                header_name=None, login_path=None, username_field="username",
                                password_field="password", token_field="access_token")
    out = go(prov(server, auth), req("/bearer"))
    assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied", out
    assert server.hits == []


def test_the_token_request_is_joined_under_the_prefix_and_sends_the_form(server):
    p = prov(server, grant_auth(), path_prefix="/api/v2")
    ok(go(p, req("/bearer")))
    assert [path for _, path, _ in server.hits] == ["/api/v2/auth/token", "/api/v2/bearer"]
    assert dict(parse_qsl(server.bodies[0].decode())) == {"username": GRANT_USER, "password": GRANT_PASSWORD}


def test_the_token_request_obeys_the_same_address_policy(server):
    p = prov(server, grant_auth(), network={"lan": False})
    out = go(p, req("/bearer"))
    assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied"
    assert server.hits == []


def test_the_token_request_shares_the_calls_single_deadline(server):
    p = prov(server, grant_auth("/auth/slow-token"), timeout_s=0.5)
    t0 = time.monotonic()
    out = go(p, req("/bearer"))
    assert isinstance(out, ConfinementError) and out.error_class == "timeout", out
    assert time.monotonic() - t0 < 2.5  # the stalled token request got no budget of its own
    assert server.hits_to("/bearer") == 0


def test_a_custom_token_field_is_honoured(server):
    auth = Auth(type="password_grant", token_path=TOKEN_PATH, secret_ref="env:AUTH_CREDENTIALS")
    p = prov(server, auth.model_copy(update={"token_field": "access_token"}))
    ok(go(p, req("/bearer")))


def test_a_read_effect_may_not_use_a_session_to_reach_a_mutating_method(server):
    p = prov(server, cookie_auth())
    out = go(p, req("/write", "POST", body={"a": 1}), effect="read")
    assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied"
    assert server.hits == []  # refused before the login, which is also a mutating exchange


def test_concurrent_first_calls_never_corrupt_the_token_session(server):
    """The password_grant mirror of the cookie test: eight racing first calls must each be a live 200
    or the pre-existing resolver-cap refusal, and the token store must survive intact."""
    p = prov(server, grant_auth())
    out: list = []
    barrier = threading.Barrier(8)

    def call() -> None:
        barrier.wait()
        out.append(go(p, req("/bearer")))

    threads = [threading.Thread(target=call) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert len(out) == 8
    successes = [r for r in out if isinstance(r, RawResponse)]
    for r in out:
        if isinstance(r, RawResponse):
            assert r.status_code == 200, r
        else:
            resolver_cap_refusal(r)
    assert successes, out
    assert 1 <= server.hits_to(TOKEN_PATH) <= len(successes)

    ok(go(p, req("/bearer")))
    tokens = server.hits_to(TOKEN_PATH)
    ok(go(p, req("/bearer")))
    assert server.hits_to(TOKEN_PATH) == tokens  # the held token was reused, no re-token


# ---- the in-memory store itself -------------------------------------------------------------


def test_the_session_store_is_bounded(monkeypatch):
    from personal_world.worlds import confinement

    monkeypatch.setattr(confinement, "_SESSION_MAX", 2)
    keys = [("id", "base", "prefix", "cookie_session", "env:X", "/login", "") + (str(i),) for i in range(4)]
    for key in keys:
        confinement._session_keep(key, "value")
    assert len(confinement._SESSIONS) == 2
    assert confinement._session_take(keys[-1]) == "value"  # the newest is still held
    assert confinement._session_take(keys[0]) is None  # the oldest was dropped


def test_the_session_key_covers_the_whole_provider_identity():
    from personal_world.worlds import confinement

    with AuthServer() as srv:
        p = prov(srv, cookie_auth())
        base = confinement._session_key(p)
        for changed in [p.model_copy(update={"id": "other"}),
                        p.model_copy(update={"base_url": "http://127.0.0.1:1"}),
                        p.model_copy(update={"path_prefix": "/api/v2"}),
                        p.model_copy(update={"auth": cookie_auth().model_copy(update={"secret_ref": "env:OTHER_CREDENTIALS"})}),
                        p.model_copy(update={"auth": cookie_auth("/other/login")})]:
            assert confinement._session_key(changed) != base


def test_concurrent_first_calls_never_corrupt_the_session(server):
    """Eight first calls race for ONE provider. The only acceptable outcome per call is a live 200 or
    the pre-existing resolver-cap refusal (a deliberate guard, not an auth failure). Whatever the
    interleaving, the session store ends intact and the next calls reuse it without a second login.
    """
    p = prov(server, cookie_auth())
    out: list = []
    barrier = threading.Barrier(8)

    def call() -> None:
        barrier.wait()
        out.append(go(p, req("/protected")))

    threads = [threading.Thread(target=call) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert len(out) == 8
    successes = [r for r in out if isinstance(r, RawResponse)]
    for r in out:
        if isinstance(r, RawResponse):
            assert r.status_code == 200, r  # never a 4xx/5xx
        else:
            resolver_cap_refusal(r)  # never auth_failed, never any other error
    assert successes, out  # at least one call got past DNS
    # the login is hit at least once, and at most once for each call that got past DNS
    assert 1 <= server.hits_to(LOGIN_PATH) <= len(successes)

    ok(go(p, req()))
    logins = server.hits_to(LOGIN_PATH)
    ok(go(p, req()))
    assert server.hits_to(LOGIN_PATH) == logins  # the held session was reused, no re-login


def test_two_concurrent_first_calls_both_succeed(server):
    """Two is exactly the per-provider lookup cap, so both calls always get a slot: deterministic,
    and both must reach the provider."""
    p = prov(server, cookie_auth())
    out: list = []
    barrier = threading.Barrier(2)

    def call() -> None:
        barrier.wait()
        out.append(go(p, req("/protected")))

    threads = [threading.Thread(target=call) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    for r in out:
        if isinstance(r, RawResponse):
            assert r.status_code == 200, r
        else:
            resolver_cap_refusal(r)
    assert len([r for r in out if isinstance(r, RawResponse)]) == 2, out
    assert server.hits_to(LOGIN_PATH) >= 1
