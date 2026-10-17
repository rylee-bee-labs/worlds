"""Acceptance tests for personal_world.worlds.runner (C2 inputs, confinement seam, last-good)."""
import json
import stat
import threading
import time

import pytest
from pydantic import ValidationError

from personal_world.worlds.confinement import ConfinementError, RawResponse
from personal_world.worlds.models import Assertion, Auth, Provider, Request
from personal_world.worlds.reference_provider import ReferenceServer, reference_send
from personal_world.worlds.runner import Runner

from .conftest import add_request, ok


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def make(store, send, clock=None, **kw):
    return Runner(store, send, clock=clock or Clock(), **kw)


def test_fetch_ok_parses_json_and_calls_send_with_read_effect(store, send):
    add_request(store)
    send.responses["/items"] = ok({"items": [1]})
    f = make(store, send).fetch("ref.items")
    assert f.ok and f.data == {"items": [1]} and f.status_code == 200 and f.error_class is None
    assert f.method == "GET" and f.path == "/items" and f.duration_ms == 7 and not f.from_cache
    assert send.calls == [("ref.items", "GET", "/items", "read")]


def test_ttl_cache_force_and_expiry(store, send):
    add_request(store, ttl_s=60)
    send.responses["/items"] = ok({"n": 1})
    clock = Clock()
    r = make(store, send, clock)
    r.fetch("ref.items")
    again = r.fetch("ref.items")
    assert again.from_cache and send.count() == 1
    r.fetch("ref.items", force=True)
    assert send.count() == 2
    clock.t += 61
    r.fetch("ref.items")
    assert send.count() == 3


def test_ttl_zero_never_caches(store, send):
    add_request(store, ttl_s=0)
    send.responses["/items"] = ok({})
    r = make(store, send)
    r.fetch("ref.items")
    r.fetch("ref.items")
    assert send.count() == 2


def test_write_request_is_refused_before_send(store, send):
    add_request(store, name="do", path="/do", method="POST")
    f = make(store, send).fetch("ref.do")
    assert not f.ok and f.error_class == "confinement_denied" and "write" in f.note
    assert send.calls == []


def test_unknown_request_never_calls_send(store, send):
    f = make(store, send).fetch("ref.nope")
    assert not f.ok and f.error_class == "confinement_denied" and send.calls == []


@pytest.mark.parametrize("status,cls", [(500, "http_5xx"), (503, "http_5xx"), (404, "http_4xx"), (422, "http_4xx"),
                                        (401, "auth_failed"), (403, "auth_failed")])
def test_http_status_classes(store, send, status, cls):
    add_request(store)
    send.responses["/items"] = RawResponse(status_code=status, body=b"x")
    f = make(store, send).fetch("ref.items")
    assert not f.ok and f.error_class == cls and f.status_code == status


def test_malformed_json_and_non_utf8(store, send):
    add_request(store)
    send.responses["/items"] = RawResponse(status_code=200, body=b"not json {")
    assert make(store, send).fetch("ref.items").error_class == "malformed"
    send.responses["/items"] = RawResponse(status_code=200, body=b"\xff\xfe")
    assert make(store, send, ).fetch("ref.items", force=True).error_class == "malformed"


def test_confinement_errors_pass_through(store, send):
    add_request(store)
    for cls in ("timeout", "connection", "redirect_refused", "too_large", "confinement_denied", "auth_failed"):
        send.responses["/items"] = ConfinementError(cls, "n")
        f = make(store, send).fetch("ref.items", force=True)
        assert not f.ok and f.error_class == cls


def test_sender_exception_never_escapes(store, send):
    add_request(store)
    send.responses["/items"] = RuntimeError("boom with s3cret-value")
    f = make(store, send, secret_values=["s3cret-value"]).fetch("ref.items")
    assert not f.ok and f.error_class == "connection"
    assert "s3cret-value" not in f.note


def test_assertions(store, send):
    add_request(store, assertions=[Assertion(status=200), Assertion(path="$.items", is_list=True),
                                   Assertion(path="$.state", equals="ok"), Assertion(path="$.state", exists=True)])
    send.responses["/items"] = ok({"items": [], "state": "ok"})
    assert make(store, send).fetch("ref.items").ok
    send.responses["/items"] = ok({"items": {}, "state": "ok"})
    f = make(store, send).fetch("ref.items", force=True)
    assert not f.ok and f.error_class == "malformed" and "assert" in f.note
    send.responses["/items"] = ok({"items": [], "state": "bad"})
    assert not make(store, send).fetch("ref.items", force=True).ok
    send.responses["/items"] = ok({"items": []})
    assert not make(store, send).fetch("ref.items", force=True).ok
    send.responses["/items"] = ok({"items": [], "state": "ok"}, status=201)
    assert not make(store, send).fetch("ref.items", force=True).ok


def test_last_good_survives_failure_and_failure_is_not_cached_as_good(store, send):
    add_request(store, ttl_s=0)
    r = make(store, send, Clock(500.0))
    send.responses["/items"] = ok({"v": 1})
    r.fetch("ref.items")
    send.responses["/items"] = RawResponse(status_code=500)
    f = r.fetch("ref.items")
    assert not f.ok
    lg = r.last_good("ref.items")
    assert lg is not None and lg[0] == {"v": 1} and lg[1] == 500.0


def test_last_good_persists_in_cache_dir_and_is_disposable(store, send, tmp_path):
    add_request(store, ttl_s=0)
    cache = tmp_path / "cache"
    send.responses["/items"] = ok({"v": 2})
    make(store, send, Clock(700.0), cache_dir=cache).fetch("ref.items")
    files = list(cache.rglob("*"))
    assert [f for f in files if f.is_file()]
    for f in files:
        if f.is_file():
            assert not stat.S_IMODE(f.stat().st_mode) & 0o077
    r2 = make(store, send, cache_dir=cache)
    assert r2.last_good("ref.items")[0] == {"v": 2}
    import shutil
    shutil.rmtree(cache)
    assert make(store, send, cache_dir=cache).last_good("ref.items") is None


def test_notes_are_redacted_and_short(store, send):
    add_request(store)
    send.responses["/items"] = ConfinementError(
        "connection", "failed with Authorization: Bearer abcdef123456 and key s3cret-value " + "x" * 5000)
    f = make(store, send, secret_values=["s3cret-value"]).fetch("ref.items")
    assert "abcdef123456" not in f.note and "s3cret-value" not in f.note and len(f.note) <= 300


def test_no_response_body_in_fetch_evidence(store, send):
    add_request(store)
    send.responses["/items"] = RawResponse(status_code=500, body=b"SECRET-BODY-" + b"z" * 5000)
    f = make(store, send).fetch("ref.items")
    assert "SECRET-BODY" not in f.note


def test_single_flight_for_concurrent_fetches(store, send):
    add_request(store, ttl_s=0)
    def slow():
        time.sleep(0.2)
        return ok({"x": 1})
    send.responses["/items"] = slow
    r = make(store, send)
    out = []
    ts = [threading.Thread(target=lambda: out.append(r.fetch("ref.items"))) for _ in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert send.count() == 1 and len(out) == 5 and all(o.ok for o in out)


# ---- cookie_session auth (T9): the session cookie lives only in the sender's memory ---------------------------

COOKIE_USERNAME = "admin"
COOKIE_PASSWORD = "pw-s3cret-cookie-9c1f"
COOKIE_LOGIN_PATH = "/api/v2/auth/login"


@pytest.fixture
def cookie_server():
    with ReferenceServer(username=COOKIE_USERNAME, password=COOKIE_PASSWORD) as srv:
        yield srv


def cookie_provider(server, **kw):
    d = dict(
        id="cookie",
        name="Cookie",
        kind="reference",
        base_url=server.base_url,
        network={"lan": True},
        auth=Auth(
            type="cookie_session",
            login_path=COOKIE_LOGIN_PATH,
            secret_ref="env:COOKIE_CREDENTIALS",
        ),
    )
    d.update(kw)
    return Provider(**d)


def cookie_secrets():
    return {"COOKIE_CREDENTIALS": f"{COOKIE_USERNAME}:{COOKIE_PASSWORD}"}


def cookie_store(store, server, path="/cookie-protected", **request_kw):
    store.save("provider", cookie_provider(server))
    store.save("request", Request(id="cookie.items", provider="cookie", path=path, **request_kw))
    return store


def test_cookie_session_login_then_authenticated_read(cookie_server, store):
    cookie_store(store, cookie_server)
    f = make(store, reference_send(cookie_secrets())).fetch("cookie.items")
    assert f.ok and f.status_code == 200 and f.data == {"ok": True, "items": [1, 2]}
    assert cookie_server.calls_to(COOKIE_LOGIN_PATH) == 1
    assert cookie_server.calls_to("/cookie-protected") == 1


def test_cookie_session_renews_on_403_exactly_once(cookie_server, store):
    cookie_store(store, cookie_server)
    runner = make(store, reference_send(cookie_secrets()))
    assert runner.fetch("cookie.items").ok
    assert cookie_server.calls_to(COOKIE_LOGIN_PATH) == 1
    cookie_server.expire_sessions()  # the server forgets the session; the sender still holds it
    f = runner.fetch("cookie.items", force=True)
    assert f.ok and f.status_code == 200
    assert cookie_server.calls_to(COOKIE_LOGIN_PATH) == 2  # exactly one re-login
    assert cookie_server.calls_to("/cookie-protected") == 3  # ok, rejected, retried once


def test_cookie_session_second_403_fails_without_looping(cookie_server, store):
    cookie_store(store, cookie_server, path="/cookie-denied")
    f = make(store, reference_send(cookie_secrets())).fetch("cookie.items")
    assert not f.ok and f.error_class == "auth_failed" and f.status_code == 403
    assert cookie_server.calls_to(COOKIE_LOGIN_PATH) == 2  # initial + one re-login, never more
    assert cookie_server.calls_to("/cookie-denied") == 2


def test_cookie_session_keeps_cookie_and_password_out_of_everything(cookie_server, store, tmp_path):
    cookie_store(store, cookie_server, ttl_s=0)
    cache = tmp_path / "cache"
    secrets_map = cookie_secrets()
    runner = make(store, reference_send(secrets_map), cache_dir=cache, secret_values=list(secrets_map.values()))
    f = runner.fetch("cookie.items")
    assert f.ok

    # The login POST carried the credential in its form body ...
    login_bodies = cookie_server.bodies_to(COOKIE_LOGIN_PATH)
    assert len(login_bodies) == 1
    assert COOKIE_USERNAME.encode() in login_bodies[0]
    assert COOKIE_PASSWORD.encode() in login_bodies[0]

    # ... but the issued session cookie and the password are nowhere the runner kept.
    cookie = cookie_server.issued_cookie()
    assert cookie is not None
    token = cookie.partition("=")[2]
    surfaces = [f.note, json.dumps(f.as_evidence()), json.dumps(f.data)]
    for path in cache.rglob("*"):
        if path.is_file():
            surfaces.append(path.read_text())
    assert surfaces  # the cache file is part of the check
    for surface in surfaces:
        assert token not in surface
        assert COOKIE_PASSWORD not in surface


def test_cookie_session_model_needs_login_path_and_secret_ref():
    with pytest.raises(ValidationError):
        Auth(type="cookie_session", secret_ref="env:COOKIE_CREDENTIALS")  # no login_path
    with pytest.raises(ValidationError):
        Auth(type="cookie_session", login_path=COOKIE_LOGIN_PATH)  # no secret_ref
    with pytest.raises(ValueError):
        Auth(type="header", header_name="Cookie", secret_ref="env:K")  # a cookie is never a request header
    auth = Auth(type="cookie_session", secret_ref="env:COOKIE_CREDENTIALS", login_path=COOKIE_LOGIN_PATH)
    assert auth.login_path == COOKIE_LOGIN_PATH and auth.type == "cookie_session"


# ---- password_grant auth (T10): the bearer token lives only in the sender's memory ---------------------------

GRANT_USERNAME = "reader"
GRANT_PASSWORD = "pw-s3cret-grant-7d2a"
GRANT_TOKEN_PATH = "/api/v2/auth/token"


@pytest.fixture
def grant_server():
    with ReferenceServer(username=GRANT_USERNAME, password=GRANT_PASSWORD) as srv:
        yield srv


def grant_provider(server, **kw):
    d = dict(
        id="grant",
        name="Grant",
        kind="reference",
        base_url=server.base_url,
        network={"lan": True},
        auth=Auth(
            type="password_grant",
            token_path=GRANT_TOKEN_PATH,
            secret_ref="env:GRANT_CREDENTIALS",
        ),
    )
    d.update(kw)
    return Provider(**d)


def grant_secrets():
    return {"GRANT_CREDENTIALS": f"{GRANT_USERNAME}:{GRANT_PASSWORD}"}


def grant_store(store, server, path="/bearer-protected", **request_kw):
    store.save("provider", grant_provider(server))
    store.save("request", Request(id="grant.items", provider="grant", path=path, **request_kw))
    return store


def test_password_grant_token_then_authenticated_read(grant_server, store):
    grant_store(store, grant_server)
    f = make(store, reference_send(grant_secrets())).fetch("grant.items")
    assert f.ok and f.status_code == 200 and f.data == {"ok": True, "items": [1, 2]}
    assert grant_server.calls_to(GRANT_TOKEN_PATH) == 1
    assert grant_server.calls_to("/bearer-protected") == 1


def test_password_grant_renews_on_401_exactly_once(grant_server, store):
    grant_store(store, grant_server)
    runner = make(store, reference_send(grant_secrets()))
    assert runner.fetch("grant.items").ok
    assert grant_server.calls_to(GRANT_TOKEN_PATH) == 1
    grant_server.rotate_tokens()  # the server forgets the token; the sender still holds it
    f = runner.fetch("grant.items", force=True)
    assert f.ok and f.status_code == 200
    assert grant_server.calls_to(GRANT_TOKEN_PATH) == 2  # exactly one re-token
    assert grant_server.calls_to("/bearer-protected") == 3  # ok, rejected, retried once


def test_password_grant_second_401_fails_without_looping(grant_server, store):
    grant_store(store, grant_server, path="/bearer-denied")
    f = make(store, reference_send(grant_secrets())).fetch("grant.items")
    assert not f.ok and f.error_class == "auth_failed" and f.status_code == 401
    assert grant_server.calls_to(GRANT_TOKEN_PATH) == 2  # initial + one re-token, never more
    assert grant_server.calls_to("/bearer-denied") == 2


def test_password_grant_keeps_token_and_password_out_of_everything(grant_server, store, tmp_path):
    grant_store(store, grant_server, ttl_s=0)
    cache = tmp_path / "cache"
    secrets_map = grant_secrets()
    runner = make(store, reference_send(secrets_map), cache_dir=cache, secret_values=list(secrets_map.values()))
    f = runner.fetch("grant.items")
    assert f.ok

    # The token POST carried the credential in its form body ...
    token_bodies = grant_server.bodies_to(GRANT_TOKEN_PATH)
    assert len(token_bodies) == 1
    assert GRANT_USERNAME.encode() in token_bodies[0]
    assert GRANT_PASSWORD.encode() in token_bodies[0]

    # ... but the issued bearer token and the password are nowhere the runner kept.
    token = grant_server.issued_token()
    assert token is not None
    surfaces = [f.note, json.dumps(f.as_evidence()), json.dumps(f.data)]
    for path in cache.rglob("*"):
        if path.is_file():
            surfaces.append(path.read_text())
    assert surfaces  # the cache file is part of the check
    for surface in surfaces:
        assert token not in surface
        assert GRANT_PASSWORD not in surface


def test_password_grant_model_needs_token_path_and_secret_ref():
    with pytest.raises(ValidationError):
        Auth(type="password_grant", secret_ref="env:GRANT_CREDENTIALS")  # no token_path
    with pytest.raises(ValidationError):
        Auth(type="password_grant", token_path=GRANT_TOKEN_PATH)  # no secret_ref
    with pytest.raises(ValueError):
        Auth(type="password_grant", secret_ref="env:G", token_path="https://elsewhere.example/token")
    with pytest.raises(ValueError):
        Auth(type="password_grant", secret_ref="env:G", token_path="/a/../b")
    with pytest.raises(ValueError):
        Auth(type="cookie_session", secret_ref="env:G", login_path="/login", token_path="/token")
    auth = Auth(type="password_grant", secret_ref="env:GRANT_CREDENTIALS", token_path=GRANT_TOKEN_PATH)
    assert auth.token_path == GRANT_TOKEN_PATH and auth.type == "password_grant"
    assert auth.token_field == "access_token"
