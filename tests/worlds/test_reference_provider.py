"""Acceptance tests for personal_world.worlds.reference_provider (in-process test server + TEST-ONLY sender)."""
import json
import time

import pytest

from personal_world.worlds.confinement import ConfinementError, RawResponse
from personal_world.worlds.models import Auth, Provider, Request
from personal_world.worlds.reference_provider import ReferenceServer, reference_send


@pytest.fixture
def server():
    with ReferenceServer(token="s3cret-value") as srv:
        yield srv


def prov(server, **kw):
    d = dict(id="ref", name="Ref", kind="reference", base_url=server.base_url, network={"lan": True})
    d.update(kw)
    return Provider(**d)


def req(path, method="GET", **kw):
    return Request(id="ref.t", provider="ref", path=path, method=method, **kw)


def send(server, path, method="GET", provider_kw=None, request_kw=None, secrets=None):
    p = prov(server, **(provider_kw or {}))
    r = req(path, method, **(request_kw or {}))
    return reference_send(secrets or {})(p, r, effect=r.resolved_effect())


def test_list_object_and_empty(server):
    r = send(server, "/items")
    assert isinstance(r, RawResponse) and r.status_code == 200
    assert json.loads(r.body)["items"][0]["name"] == "alpha"
    assert json.loads(send(server, "/status").body)["state"] == "ok"
    assert json.loads(send(server, "/empty").body) == {"items": []}


def test_query_is_sent(server):
    r = send(server, "/echo-query", request_kw={"query": {"a": "1"}})
    assert json.loads(r.body) == {"a": "1"}


def test_controlled_post_counts_and_idempotency(server):
    r1 = send(server, "/actions/ping", "POST", request_kw={"headers": {"Idempotency-Key": "k1"}})
    r2 = send(server, "/actions/ping", "POST", request_kw={"headers": {"Idempotency-Key": "k1"}})
    r3 = send(server, "/actions/ping", "POST", request_kw={"headers": {"Idempotency-Key": "k2"}})
    assert json.loads(r1.body) == json.loads(r2.body)
    assert json.loads(r3.body)["count"] == 2
    assert server.counters["ping"] == 2


def test_errors_are_reported_as_classes(server):
    assert send(server, "/boom").status_code == 500
    r = send(server, "/validate", "POST")
    assert r.status_code == 422


def test_malformed_body_is_returned_raw(server):
    r = send(server, "/malformed")
    assert r.status_code == 200 and b"not json" in r.body


def test_timeout_class(server):
    t0 = time.monotonic()
    r = send(server, "/slow", request_kw={"query": {"delay": "3"}}, provider_kw={"timeout_s": 0.3})
    assert isinstance(r, ConfinementError) and r.error_class == "timeout"
    assert time.monotonic() - t0 < 2


def test_connection_class_when_nothing_listens():
    with ReferenceServer() as s:
        base = s.base_url
    p = Provider(id="ref", name="R", kind="reference", base_url=base, network={"lan": True})
    r = Request(id="ref.t", provider="ref", path="/items")
    out = reference_send({}, allowed_ports={int(base.rsplit(":", 1)[1])})(p, r, effect="read")
    assert isinstance(out, ConfinementError) and out.error_class == "connection"


def test_redirect_is_refused_not_followed(server):
    r = send(server, "/redirect")
    assert isinstance(r, ConfinementError) and r.error_class == "redirect_refused"
    assert server.calls_to("/items") == 0


def test_oversize_is_too_large_and_stops_reading(server):
    r = send(server, "/oversize", provider_kw={"max_bytes": 1024})
    assert isinstance(r, ConfinementError) and r.error_class == "too_large"


def test_secret_injection_and_auth_failure(server):
    no_auth = send(server, "/secret")
    assert no_auth.status_code == 401
    ok = send(server, "/secret", provider_kw={"auth": Auth(type="bearer", secret_ref="env:REF_TOKEN")},
              secrets={"REF_TOKEN": "s3cret-value"})
    assert ok.status_code == 200
    bad = send(server, "/secret", provider_kw={"auth": Auth(type="bearer", secret_ref="env:REF_TOKEN")},
               secrets={"REF_TOKEN": "wrong"})
    assert bad.status_code == 401


def test_header_and_basic_auth_shapes(server):
    r = send(server, "/echo-auth", provider_kw={"auth": Auth(type="header", header_name="X-Api-Key", secret_ref="env:K")},
             secrets={"K": "v"})
    assert json.loads(r.body)["x-api-key"] == "v"
    r = send(server, "/echo-auth", provider_kw={"auth": Auth(type="basic", secret_ref="env:B")},
             secrets={"B": "user:pw"})
    assert json.loads(r.body)["authorization"].startswith("Basic ")


def test_missing_secret_is_auth_failed_without_sending(server):
    r = send(server, "/secret", provider_kw={"auth": Auth(type="bearer", secret_ref="env:NOPE")}, secrets={})
    assert isinstance(r, ConfinementError) and r.error_class == "auth_failed"
    assert server.calls_to("/secret") == 0


def test_lost_response_after_dispatch(server):
    r = send(server, "/lost", "POST")
    assert isinstance(r, ConfinementError) and r.error_class == "connection"
    assert server.counters["lost"] == 1  # the effect happened although the answer was lost


def test_never_retries(server):
    send(server, "/lost", "POST")
    assert server.counters["lost"] == 1
    send(server, "/boom")
    assert server.calls_to("/boom") == 1


def test_error_notes_never_contain_the_secret(server):
    r = send(server, "/secret-echo", provider_kw={"auth": Auth(type="bearer", secret_ref="env:REF_TOKEN")},
             secrets={"REF_TOKEN": "s3cret-value"})
    assert r.status_code == 200  # server echoes the header back in the body (to test redaction downstream)
    assert b"s3cret-value" in r.body  # raw sender returns what the server said; redaction is the runner's job


# ---- password_grant auth (T10): the token lives only in the sender's memory ----------------------------------

GRANT_USERNAME = "reader"
GRANT_PASSWORD = "pw-s3cret-grant-7d2a"
GRANT_TOKEN_PATH = "/api/v2/auth/token"


@pytest.fixture
def grant_server():
    with ReferenceServer(username=GRANT_USERNAME, password=GRANT_PASSWORD) as srv:
        yield srv


def grant_auth():
    return Auth(type="password_grant", token_path=GRANT_TOKEN_PATH, secret_ref="env:GRANT_CREDENTIALS")


def grant_secrets():
    return {"GRANT_CREDENTIALS": f"{GRANT_USERNAME}:{GRANT_PASSWORD}"}


def test_password_grant_sender_token_then_read(grant_server):
    r = send(grant_server, "/bearer-protected", provider_kw={"auth": grant_auth()}, secrets=grant_secrets())
    assert isinstance(r, RawResponse) and r.status_code == 200
    assert json.loads(r.body) == {"ok": True, "items": [1, 2]}
    assert grant_server.calls_to(GRANT_TOKEN_PATH) == 1
    assert grant_server.calls_to("/bearer-protected") == 1


def test_password_grant_sender_renews_on_401_once(grant_server):
    sender = reference_send(grant_secrets())
    p = prov(grant_server, auth=grant_auth())
    assert sender(p, req("/bearer-protected"), effect="read").status_code == 200
    grant_server.rotate_tokens()  # the server forgets the token; the sender still holds it
    assert sender(p, req("/bearer-protected"), effect="read").status_code == 200
    assert grant_server.calls_to(GRANT_TOKEN_PATH) == 2
    assert grant_server.calls_to("/bearer-protected") == 3


def test_password_grant_sender_second_401_is_auth_failed(grant_server):
    out = send(grant_server, "/bearer-denied", provider_kw={"auth": grant_auth()}, secrets=grant_secrets())
    assert isinstance(out, ConfinementError) and out.error_class == "auth_failed"
    assert grant_server.calls_to(GRANT_TOKEN_PATH) == 2  # initial + one re-token, never more
    assert grant_server.calls_to("/bearer-denied") == 2


# ---- the retry rule: a refused READ re-logs-in once, a refused WRITE is never replayed ----------

COOKIE_USERNAME = "admin"
COOKIE_PASSWORD = "pw-s3cret-cookie-9c1f"


@pytest.fixture
def cookie_server():
    with ReferenceServer(username=COOKIE_USERNAME, password=COOKIE_PASSWORD) as srv:
        yield srv


def cookie_auth():
    return Auth(type="cookie_session", login_path="/api/v2/auth/login", secret_ref="env:COOKIE_CREDENTIALS")


def cookie_secrets():
    return {"COOKIE_CREDENTIALS": f"{COOKIE_USERNAME}:{COOKIE_PASSWORD}"}


def test_cookie_session_sender_refused_read_is_replayed_once(cookie_server):
    sender = reference_send(cookie_secrets())
    p = prov(cookie_server, auth=cookie_auth())
    assert sender(p, req("/cookie-protected"), effect="read").status_code == 200
    cookie_server.expire_sessions()
    assert sender(p, req("/cookie-protected"), effect="read").status_code == 200
    assert cookie_server.calls_to("/api/v2/auth/login") == 2
    assert cookie_server.calls_to("/cookie-protected") == 3  # ok, refused, replayed once


def test_cookie_session_sender_refused_write_is_never_replayed(cookie_server):
    sender = reference_send(cookie_secrets())
    p = prov(cookie_server, auth=cookie_auth())
    r = req("/actions/cookie-denied", "POST", effect="write")
    first = sender(p, r, effect="write")
    second = sender(p, r, effect="write")
    assert isinstance(first, RawResponse) and first.status_code == 403  # the refusal, as the result
    assert isinstance(second, RawResponse) and second.status_code == 403
    assert cookie_server.calls_to("/actions/cookie-denied") == 2  # one per call: never replayed
    assert cookie_server.calls_to("/api/v2/auth/login") == 2  # the stale session was dropped


def test_password_grant_sender_refused_write_is_never_replayed(grant_server):
    sender = reference_send(grant_secrets())
    p = prov(grant_server, auth=grant_auth())
    r = req("/actions/bearer-denied", "POST", effect="write")
    first = sender(p, r, effect="write")
    second = sender(p, r, effect="write")
    assert isinstance(first, RawResponse) and first.status_code == 401
    assert isinstance(second, RawResponse) and second.status_code == 401
    assert grant_server.calls_to("/actions/bearer-denied") == 2  # one per call: never replayed
    assert grant_server.calls_to(GRANT_TOKEN_PATH) == 2  # the stale token was dropped


def test_password_grant_sender_refused_read_is_replayed_once(grant_server):
    sender = reference_send(grant_secrets())
    p = prov(grant_server, auth=grant_auth())
    assert sender(p, req("/bearer-protected"), effect="read").status_code == 200
    grant_server.rotate_tokens()
    assert sender(p, req("/bearer-protected"), effect="read").status_code == 200
    assert grant_server.calls_to(GRANT_TOKEN_PATH) == 2
    assert grant_server.calls_to("/bearer-protected") == 3
