"""Tests for personal_world.worlds.auth_routes and owner policy (fail closed, owner allow-list)."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_world.oidc import FLOW_COOKIE, OIDCLoginError, VerifiedIdentity
from personal_world.worlds.auth_routes import (
    ESCAPE_SUCCESS_GAP,
    EVAL_GAP,
    FREE_FAILURES,
    FRESH_AUTH_SECONDS,
    GLOBAL_CEILING,
    GLOBAL_GAP,
    MAX_BACKOFF,
    OIDC_LOGIN_KEY,
    client_key,
    parse_trusted_proxies,
    register_auth_routes,
)
from personal_world.worlds.authn import SESSION_COOKIE, Auth, load_csrf_key
from personal_world.worlds.db import Database
from personal_world.worlds.owner import load_owner_policy

ORIGIN = "https://worlds.example.test"
ISSUER = "https://auth.example.test"
BOOT = "open-sesame-correct-horse-1"  # pw-safety: synthetic
OWNER_SUB = "owner-subject-123"


class Clock:
    t = 2_000_000.0

    def __call__(self):
        return self.t


class FakeClient:
    def __init__(self):
        self.redirect_uris = []
        self.identity = VerifiedIdentity(sub=OWNER_SUB, issuer=ISSUER, auth_time=Clock.t)
        self.raise_on_complete = None

    def start_login(self, redirect_uri, link_to=None, step_up_for=None, return_to=None):
        self.redirect_uris.append(redirect_uri)
        pending = SimpleNamespace(state="st", step_up_for=step_up_for, return_to=return_to)
        self.pending = pending
        return f"{ISSUER}/authorize?state=st", pending, "flowcookie"

    def read_pending(self, cookie):
        if cookie != "flowcookie":
            raise OIDCLoginError("bad flow", error_code="oidc_state_mismatch")
        return self.pending

    def complete_login(self, code, pending):
        if self.raise_on_complete:
            raise self.raise_on_complete
        return self.identity


def write_policy(cfg, *, oidc=True, bootstrap=True):
    lines = ["schema_version: 1", f"public_origin: {ORIGIN}"]
    if oidc:
        lines += ["oidc:", f"  issuer: {ISSUER}", f"  subject: {OWNER_SUB}"]
    if bootstrap:
        lines += ["bootstrap:", "  enabled: true", "  secret_ref: env:PW_TEST_BOOTSTRAP"]
    (cfg / "owner.yaml").write_text("\n".join(lines) + "\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    write_policy(cfg)
    clock = Clock()
    db = Database.in_dir(tmp_path / "data")
    auth = Auth(db, load_csrf_key(tmp_path / "data"), frozenset({ORIGIN}), clock=clock,
                binding=lambda: load_owner_policy(cfg).binding())
    fake = FakeClient()
    service = SimpleNamespace(client=lambda: fake)
    app = FastAPI()
    register_auth_routes(app, auth, lambda: load_owner_policy(cfg), service)
    c = TestClient(app, base_url=ORIGIN, follow_redirects=False)
    return SimpleNamespace(auth=auth, c=c, fake=fake, clock=clock, cfg=cfg, tmp=tmp_path)


def boot(e, token=BOOT, origin=ORIGIN):
    return e.c.post("/api/auth/bootstrap", json={"token": token}, headers={"Origin": origin} if origin else {})


def test_policy_fails_closed_when_missing_or_invalid(tmp_path):
    assert load_owner_policy(tmp_path).file is None
    (tmp_path / "owner.yaml").write_text("schema_version: 2\npublic_origin: https://x.test\n")
    assert load_owner_policy(tmp_path).file is None
    (tmp_path / "owner.yaml").write_text("schema_version: 1\npublic_origin: https://x.test/path\n")
    assert load_owner_policy(tmp_path).file is None
    (tmp_path / "owner.yaml").write_text("schema_version: 1\npublic_origin: https://u:p@x.test\n")
    assert load_owner_policy(tmp_path).file is None
    p = load_owner_policy(tmp_path)
    assert not p.is_owner_identity("a", "b") and not p.bootstrap_matches("x")


def test_session_info_unauthenticated_leaks_nothing(env):
    r = env.c.get("/api/auth/session").json()
    assert r == {"authenticated": False, "oidc_available": True, "bootstrap_available": True}


def test_bootstrap_requires_origin_and_right_secret(env):
    assert boot(env, origin=None).status_code == 403
    assert boot(env, origin="https://evil.example").status_code == 403
    assert boot(env, token="wrong").status_code == 401
    assert SESSION_COOKIE not in env.c.cookies
    r = boot(env)
    assert r.status_code == 200
    set_cookie = " ".join(r.headers.get_list("set-cookie")).lower()
    assert "httponly" in set_cookie and "secure" in set_cookie and "samesite=lax" in set_cookie
    assert "samesite=strict" in set_cookie
    info = env.c.get("/api/auth/session").json()
    assert info["authenticated"] and info["principal"] == "owner" and info["step_up"] is False and info["csrf_token"]


def boot_from(env, ip, token="nope"):
    from fastapi.testclient import TestClient
    c = TestClient(env.c.app, base_url=ORIGIN, follow_redirects=False, client=(ip, 5555))
    return c, c.post("/api/auth/bootstrap", json={"token": token}, headers={"Origin": ORIGIN})


def test_bootstrap_backoff_is_per_client_and_exponential(env):
    attacker = "203.0.113.7"
    for _ in range(FREE_FAILURES):
        assert boot_from(env, attacker)[1].status_code == 401          # the first few guesses cost nothing
    c, r = boot_from(env, attacker)
    assert r.status_code == 401                                          # this one arms the delay
    r = c.post("/api/auth/bootstrap", json={"token": "nope"}, headers={"Origin": ORIGIN})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 5   # back-off: refused, no hint
    # the owner, from another address, is not held back by the attacker
    owner_c, ok = boot_from(env, "198.51.100.9", token=BOOT)
    assert ok.status_code == 200
    # every further wrong guess doubles the delay (capped); waiting it out makes the client normal again
    def wrong():
        env.clock.t += EVAL_GAP + 0.1
        return c.post("/api/auth/bootstrap", json={"token": "nope"}, headers={"Origin": ORIGIN})

    first, second, third = (int(wrong().headers["retry-after"]) for _ in range(3))
    assert first < second < third
    env.clock.t += third + 1
    assert boot_from(env, attacker, BOOT)[1].status_code == 200          # out of back-off: the right secret just works


def test_backoff_is_capped(env):
    ip = "203.0.113.50"
    for _ in range(40):
        env.clock.t += MAX_BACKOFF + 1
        boot_from(env, ip)
    c, _ = boot_from(env, ip)
    r = c.post("/api/auth/bootstrap", json={"token": "x"}, headers={"Origin": ORIGIN})
    assert r.status_code == 429 and int(r.headers["retry-after"]) <= int(MAX_BACKOFF) + 1


def test_owner_can_escape_a_back_off_they_did_not_cause_once_per_15_minutes(env):
    shared = "192.0.2.77"                                                 # e.g. an untrusted proxy: everyone is this address
    right = BOOT
    for _ in range(FREE_FAILURES + 1):
        boot_from(env, shared)
    c, wrong = boot_from(env, shared)
    assert wrong.status_code == 429                                       # the key is in back-off
    env.clock.t += EVAL_GAP + 0.1
    assert c.post("/api/auth/bootstrap", json={"token": "wrong-guess"}, headers={"Origin": ORIGIN}).status_code == 429
    env.clock.t += EVAL_GAP + 0.1
    ok = c.post("/api/auth/bootstrap", json={"token": right}, headers={"Origin": ORIGIN})
    assert ok.status_code == 200 and SESSION_COOKIE in ok.headers.get("set-cookie", "")   # the owner got in, no waiting
    for _ in range(FREE_FAILURES + 1):                                    # the attacker puts the key back in back-off
        boot_from(env, shared)
    env.clock.t += EVAL_GAP + 0.1
    again = c.post("/api/auth/bootstrap", json={"token": right}, headers={"Origin": ORIGIN})
    assert again.status_code == 429                                       # but only ONE escape per 15 minutes
    env.clock.t += ESCAPE_SUCCESS_GAP + 1
    assert c.post("/api/auth/bootstrap", json={"token": right}, headers={"Origin": ORIGIN}).status_code == 200


def test_an_attacker_flooding_from_another_key_cannot_starve_the_owner(env):
    for i in range(300):                                                  # a flood with no pauses at all (the clock never moves)
        boot_from(env, f"203.0.113.{i % 200 + 1}", token=f"guess-{i}")
    assert boot_from(env, "198.51.100.30", BOOT)[1].status_code == 200    # the owner's correct secret still gets in
    _, again = boot_from(env, "198.51.100.31", BOOT)                      # (a fresh key is not in back-off at all)
    assert again.status_code in (200, 429)
    shared = "192.0.2.99"                                                 # and when the owner shares the attacker's key
    for _ in range(100):
        boot_from(env, shared, token="spam")
    env.clock.t += ESCAPE_SUCCESS_GAP + 1                                 # within one 15-minute window the success slot is free
    c, r = boot_from(env, shared, BOOT)
    assert r.status_code == 200


def test_wrong_guesses_in_back_off_lengthen_it_but_never_block_the_owner(env):
    ip = "192.0.2.55"
    for _ in range(FREE_FAILURES + 1):
        boot_from(env, ip)
    c, _ = boot_from(env, ip)

    def wrong():
        env.clock.t += EVAL_GAP + 0.1
        return c.post("/api/auth/bootstrap", json={"token": "x"}, headers={"Origin": ORIGIN})

    first = int(wrong().headers["retry-after"])
    for _ in range(3):
        wrong()
    later = int(wrong().headers["retry-after"])
    assert later > first
    env.clock.t += EVAL_GAP + 0.1
    assert c.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN}).status_code == 200


def test_bootstrap_comparison_does_not_depend_on_length(env, monkeypatch):
    import personal_world.worlds.owner as owner_mod
    seen = []
    real = owner_mod.hmac.compare_digest
    monkeypatch.setattr(owner_mod.hmac, "compare_digest", lambda a, b: seen.append((len(a), len(b))) or real(a, b))
    pol = owner_mod.load_owner_policy(env.cfg)
    pol.bootstrap_matches("x")
    pol.bootstrap_matches("x" * 500)
    assert seen and all(pair == (32, 32) for pair in seen)               # sha256 digests on both sides, always


@pytest.mark.parametrize("weak", ["short-secret", "open sesame correct horse", "x" * 21, "correct.horse.battery.staple.9", "a1b2c3d4" * 3])
def test_weak_bootstrap_secrets_are_refused_outright(env, monkeypatch, weak):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", weak)
    assert boot_from(env, "198.51.100.1", weak)[1].status_code == 401


@pytest.mark.parametrize("strong", ["a" * 32, "0123456789abcdef0123456789abcdef", "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5", "x" * 22])
def test_strong_bootstrap_secrets_are_accepted(env, monkeypatch, strong):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", strong)
    assert boot_from(env, "198.51.100.1", strong)[1].status_code == 200


def test_in_back_off_a_key_gets_one_evaluated_guess_per_gap_and_the_rest_are_not_compared(env, monkeypatch):
    ip = "203.0.113.9"
    for _ in range(FREE_FAILURES + 1):
        boot_from(env, ip)
    calls = []
    import personal_world.worlds.owner as owner_mod
    real = owner_mod.OwnerPolicy.bootstrap_matches
    monkeypatch.setattr(owner_mod.OwnerPolicy, "bootstrap_matches", lambda self, t: calls.append(t) or real(self, t))
    c, _ = boot_from(env, ip)
    calls.clear()
    env.clock.t += EVAL_GAP + 0.1
    for i in range(400):                                                   # ~ hundreds of guesses per second, clock frozen
        c.post("/api/auth/bootstrap", json={"token": f"guess-{i}"}, headers={"Origin": ORIGIN})
    assert len(calls) == 1                                                 # only one was even compared (the first, then the gap)
    r = c.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN})
    assert r.status_code == 429 and len(calls) == 1                        # the right secret inside the gap is not compared either
    env.clock.t += EVAL_GAP + 0.1
    assert c.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN}).status_code == 200


def test_the_eval_gap_is_per_key_so_the_owner_on_her_own_key_cannot_be_starved(env):
    for _ in range(FREE_FAILURES + 1):
        boot_from(env, "203.0.113.9")
    c, _ = boot_from(env, "203.0.113.9")
    for i in range(500):
        c.post("/api/auth/bootstrap", json={"token": f"g{i}"}, headers={"Origin": ORIGIN})   # the attacker hammers its own key
    assert boot_from(env, "198.51.100.40", BOOT)[1].status_code == 200                       # the owner's key is independent


def test_five_thousand_failures_never_overflow(env):
    ip = "203.0.113.77"
    c, _ = boot_from(env, ip)
    for _ in range(5000):
        env.clock.t += EVAL_GAP + 0.1
        r = c.post("/api/auth/bootstrap", json={"token": "x"}, headers={"Origin": ORIGIN})
        assert r.status_code in (401, 429)                                 # never a 500
    assert int(r.headers["retry-after"]) <= int(MAX_BACKOFF) + 1
    env.clock.t += EVAL_GAP + 0.1
    assert c.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN}).status_code == 200


def test_global_ceiling_slows_but_never_locks_the_owner_out(env):
    for i in range(GLOBAL_CEILING + 1):                                   # a botnet: many addresses, one guess each
        boot_from(env, f"192.0.2.{i % 250 + 1}")
    _, fast = boot_from(env, "198.51.100.77", token=BOOT)
    _, again = boot_from(env, "198.51.100.78", token=BOOT)
    assert 429 in (fast.status_code, again.status_code)                   # attempts are spaced out...
    env.clock.t += GLOBAL_GAP + 0.1
    _, later = boot_from(env, "198.51.100.79", token=BOOT)
    assert later.status_code == 200                                        # ...but the owner gets through


def test_oidc_login_is_never_blocked_by_bootstrap_lockout(env):
    for _ in range(FREE_FAILURES + 3):
        boot_from(env, "203.0.113.7")
    cb = login_via_oidc(env)
    assert cb.status_code == 303 and env.c.get("/api/auth/session").json()["authenticated"]


def test_sessions_end_when_the_owner_identity_changes(env):
    login_via_oidc(env)
    assert env.c.get("/api/auth/session").json()["authenticated"]
    (env.cfg / "owner.yaml").write_text((env.cfg / "owner.yaml").read_text().replace(OWNER_SUB, "someone-else"))
    assert env.c.get("/api/auth/session").json()["authenticated"] is False


def test_bootstrap_switches_itself_off_once_oidc_has_worked(env):
    assert boot_from(env, "198.51.100.1", BOOT)[1].status_code == 200   # before OIDC has worked: fine
    assert env.c.get("/api/auth/session").json()["bootstrap_available"] is True
    login_via_oidc(env)
    assert env.auth.get_state(OIDC_LOGIN_KEY)
    assert env.c.get("/api/auth/session").json()["bootstrap_available"] is False
    assert boot_from(env, "198.51.100.2", BOOT)[1].status_code == 401   # bootstrap sign-in is off now
    sid = env.c.cookies.get(SESSION_COOKIE)
    h = {"Origin": ORIGIN, "X-CSRF-Token": env.auth.csrf_token(sid)}
    assert env.c.post("/api/auth/step-up", json={"token": BOOT}, headers=h).status_code == 401   # and so is its step-up


def test_bootstrap_stays_available_when_oidc_is_configured_but_never_used(env):
    assert env.c.get("/api/auth/session").json()["bootstrap_available"] is True
    assert boot_from(env, "198.51.100.1", BOOT)[1].status_code == 200


def test_bootstrap_disabled_without_policy(env):
    (env.cfg / "owner.yaml").unlink()
    assert boot(env).status_code == 401


def test_step_up_with_bootstrap_secret_needs_session_csrf(env):
    boot(env)
    sid = env.c.cookies.get(SESSION_COOKIE)
    h = {"Origin": ORIGIN, "X-CSRF-Token": env.auth.csrf_token(sid)}
    assert env.c.post("/api/auth/step-up", json={"token": BOOT}).status_code == 403   # no origin/csrf
    assert env.c.post("/api/auth/step-up", json={"token": "bad"}, headers=h).status_code == 401
    assert env.c.post("/api/auth/step-up", json={"token": BOOT}, headers=h).status_code == 200
    assert env.c.get("/api/auth/session").json()["step_up"] is True


def test_logout_invalidates_server_side(env):
    boot(env)
    sid = env.c.cookies.get(SESSION_COOKIE)
    h = {"Origin": ORIGIN, "X-CSRF-Token": env.auth.csrf_token(sid)}
    assert env.c.post("/api/auth/logout").status_code == 403
    assert env.c.post("/api/auth/logout", headers=h).status_code == 200
    assert env.auth.sessions.get(sid) is None


def login_via_oidc(e):
    r = e.c.get("/api/auth/oidc/login")
    assert r.status_code == 303 and r.headers["location"].startswith(ISSUER)
    e.c.cookies.set(FLOW_COOKIE, "flowcookie")
    return e.c.get("/api/auth/oidc/callback", params={"code": "c", "state": "st"})


def test_oidc_owner_gets_a_session_and_redirect_uri_ignores_host_header(env):
    env.c.get("/api/auth/oidc/login", headers={"Host": "evil.example"})
    assert env.fake.redirect_uris == [f"{ORIGIN}/api/auth/oidc/callback"]
    cb = login_via_oidc(env)
    assert cb.status_code == 303 and cb.headers["location"] == "/"
    assert env.c.get("/api/auth/session").json()["authenticated"]


@pytest.mark.parametrize("iss,sub", [(ISSUER, "someone-else"), ("https://other.example", OWNER_SUB), ("", OWNER_SUB), (ISSUER, "")])
def test_oidc_non_owner_is_refused_without_session(env, iss, sub):
    env.fake.identity = VerifiedIdentity(sub=sub, issuer=iss, auth_time=env.clock.t)
    cb = login_via_oidc(env)
    assert cb.status_code == 403 and SESSION_COOKIE not in cb.headers.get("set-cookie", "")
    assert env.c.get("/api/auth/session").json()["authenticated"] is False


def test_oidc_state_mismatch_and_provider_error_and_failures(env):
    env.c.get("/api/auth/oidc/login")
    env.c.cookies.set(FLOW_COOKIE, "flowcookie")
    refused = (400, 403)
    assert env.c.get("/api/auth/oidc/callback", params={"code": "c", "state": "WRONG"}).status_code in refused
    assert env.c.get("/api/auth/oidc/callback", params={"error": "access_denied"}).status_code in refused
    env.fake.raise_on_complete = OIDCLoginError("boom", error_code="oidc_token_exchange_failed")
    assert env.c.get("/api/auth/oidc/callback", params={"code": "c", "state": "st"}).status_code in refused
    env.c.cookies.delete(FLOW_COOKIE)
    assert env.c.get("/api/auth/oidc/callback", params={"code": "c", "state": "st"}).status_code in refused
    assert env.c.get("/api/auth/session").json()["authenticated"] is False


def test_oidc_unconfigured_is_503_and_never_signs_in(env):
    write_policy(env.cfg, oidc=False)
    assert env.c.get("/api/auth/oidc/login").status_code == 503
    assert env.c.get("/api/auth/oidc/callback", params={"code": "c", "state": "st"}).status_code == 503


def test_oidc_step_up_needs_fresh_auth_by_the_owner_in_the_same_session(env):
    login_via_oidc(env)
    r = env.c.get("/api/auth/oidc/step-up", params={"return_to": "//evil.example/x"})
    assert r.status_code == 303 and env.fake.pending.return_to == "/"          # open redirect refused
    env.c.cookies.set(FLOW_COOKIE, "flowcookie")
    env.fake.identity = VerifiedIdentity(sub=OWNER_SUB, issuer=ISSUER, auth_time=env.clock.t - FRESH_AUTH_SECONDS - 5)
    assert env.c.get("/api/auth/oidc/callback", params={"code": "c", "state": "st"}).status_code == 403  # stale auth_time
    assert env.c.get("/api/auth/session").json()["step_up"] is False
    env.c.get("/api/auth/oidc/step-up", params={"return_to": "/connect"})
    env.c.cookies.set(FLOW_COOKIE, "flowcookie")
    env.fake.identity = VerifiedIdentity(sub=OWNER_SUB, issuer=ISSUER, auth_time=env.clock.t - 5)
    ok = env.c.get("/api/auth/oidc/callback", params={"code": "c", "state": "st"})
    assert ok.status_code == 303 and ok.headers["location"] == "/connect"
    assert env.c.get("/api/auth/session").json()["step_up"] is True


def test_oidc_step_up_requires_a_session(env):
    assert env.c.get("/api/auth/oidc/step-up").status_code == 401


# ----------------------------------------------------- trusted proxies (review #237)
def _req(peer, xff=None):
    from starlette.requests import Request
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers, "client": (peer, 1234)})


def test_client_key_without_trusted_proxies_is_the_peer_and_warns_once(caplog):
    import personal_world.worlds.auth_routes as ar
    ar._warned["xff"] = False
    with caplog.at_level("WARNING"):
        assert client_key(_req("192.0.2.10", "203.0.113.5"), ()) == "192.0.2.10"
        assert client_key(_req("192.0.2.10", "203.0.113.6"), ()) == "192.0.2.10"
    assert len([m for m in caplog.messages if "PW_TRUSTED_PROXIES" in m]) == 1
    ar._warned["xff"] = False
    caplog.clear()
    with caplog.at_level("WARNING"):
        client_key(_req("127.0.0.1", "203.0.113.5"), ())             # loopback peers do not warn
        client_key(_req("192.0.2.10"), ())                           # no X-Forwarded-For: nothing to warn about
    assert not caplog.messages


def test_client_key_behind_trusted_proxies_uses_the_right_most_untrusted_hop():
    trusted = parse_trusted_proxies("192.0.2.10, 192.0.2.0/28")
    assert client_key(_req("192.0.2.10", "203.0.113.5"), trusted) == "203.0.113.5"
    assert client_key(_req("192.0.2.10", "203.0.113.5, 192.0.2.11"), trusted) == "203.0.113.5"      # inner proxy hop skipped
    assert client_key(_req("192.0.2.10", "198.51.100.200, 203.0.113.5"), trusted) == "203.0.113.5"  # spoofed left side ignored
    assert client_key(_req("192.0.2.10"), trusted) == "192.0.2.10"                                   # nothing forwarded
    assert client_key(_req("192.0.2.10", "garbage, 203.0.113.5"), trusted) == "203.0.113.5"
    assert client_key(_req("192.0.2.10", "203.0.113.5, garbage"), trusted) == "192.0.2.10"           # garbage next to us: trust none
    assert client_key(_req("198.51.100.99", "203.0.113.5"), trusted) == "198.51.100.99"              # peer is not a proxy: XFF ignored
    assert client_key(_req("192.0.2.10", "192.0.2.11, 192.0.2.12"), trusted) == "192.0.2.10"         # all hops trusted


def test_parse_trusted_proxies():
    assert parse_trusted_proxies("") == () and parse_trusted_proxies(None) == ()
    assert len(parse_trusted_proxies("192.0.2.1, 198.51.100.0/24")) == 2
    with pytest.raises(ValueError):
        parse_trusted_proxies("192.0.2.1, not-an-ip")


def test_with_trusted_proxies_clients_behind_the_proxy_have_separate_limits(env):
    from fastapi.testclient import TestClient
    trusted = parse_trusted_proxies("192.0.2.10")
    app = FastAPI()
    register_auth_routes(app, env.auth, lambda: load_owner_policy(env.cfg), None, trusted_proxies=trusted)
    proxy = TestClient(app, base_url=ORIGIN, follow_redirects=False, client=("192.0.2.10", 1))

    def attempt(who, token):
        return proxy.post("/api/auth/bootstrap", json={"token": token},
                          headers={"Origin": ORIGIN, "X-Forwarded-For": who})

    for _ in range(FREE_FAILURES + 1):
        attempt("203.0.113.5", "nope")
    assert attempt("203.0.113.5", "nope").status_code == 429               # the attacker is in back-off
    assert attempt("198.51.100.20", BOOT).status_code == 200   # the owner behind the same proxy is not


def _req_multi(peer, lines):
    from starlette.requests import Request
    return Request({"type": "http", "method": "POST", "path": "/", "client": (peer, 1),
                    "headers": [(b"x-forwarded-for", line.encode()) for line in lines]})


def test_every_x_forwarded_for_line_is_read_in_order_and_ports_are_stripped():
    trusted = parse_trusted_proxies("192.0.2.10")
    assert client_key(_req_multi("192.0.2.10", ["198.51.100.200", "203.0.113.5"]), trusted) == "203.0.113.5"   # a second header line
    assert client_key(_req_multi("192.0.2.10", ["203.0.113.5", "192.0.2.10"]), trusted) == "203.0.113.5"
    assert client_key(_req("192.0.2.10", "203.0.113.5:51234"), trusted) == "203.0.113.5"
    assert client_key(_req("192.0.2.10", "203.0.113.5:51234, 192.0.2.10:443"), trusted) == "203.0.113.5"       # proxy hop with a port
    assert client_key(_req("192.0.2.10", "[2001:db8::5]:443"), trusted) == "2001:db8::5"
    assert client_key(_req("192.0.2.10", "[2001:db8::5]"), trusted) == "2001:db8::5"
    assert client_key(_req("192.0.2.10", "2001:db8::5"), trusted) == "2001:db8::5"
