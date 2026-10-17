"""Tests for personal_world.worlds.authn (sessions, agent tokens, CSRF, fail-closed)."""
import os
import stat

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from personal_world.worlds.authn import (
    ABSOLUTE_SECONDS,
    CSRF_COOKIE,
    IDLE_SECONDS,
    SESSION_COOKIE,
    Auth,
    Principal,
    load_csrf_key,
    load_key,
    principal_dependency,
)
from personal_world.worlds.db import Database

ORIGIN = "https://worlds.example.test"


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path):
    clock = Clock()
    db = Database.in_dir(tmp_path)
    auth = Auth(db, load_csrf_key(tmp_path), frozenset({ORIGIN}), clock=clock)
    app = FastAPI()
    owner = principal_dependency(auth)
    anyone = principal_dependency(auth, owner_only=False)

    @app.get("/own")
    def own(p: Principal = Depends(owner)):
        return {"id": p.id, "step_up": p.has_step_up(clock())}

    @app.post("/own")
    def own_post(p: Principal = Depends(owner)):
        return {"ok": True}

    @app.get("/any")
    def any_get(p: Principal = Depends(anyone)):
        return {"kind": p.kind, "scopes": list(p.scopes)}

    @app.post("/any")
    def any_post(p: Principal = Depends(anyone)):
        return {"kind": p.kind}

    return auth, TestClient(app, base_url="https://worlds.example.test"), clock, tmp_path


def login(auth, client):
    sid = auth.sessions.create("owner", "oidc")
    client.cookies.set(SESSION_COOKIE, sid)
    client.cookies.set(CSRF_COOKIE, auth.csrf_token(sid))
    return sid


def post(client, auth, sid, path="/own", origin=ORIGIN, csrf="derive", **kw):
    h = {}
    if origin is not None:
        h["Origin"] = origin
    token = auth.csrf_token(sid) if csrf == "derive" else csrf
    if token is not None:
        h["X-CSRF-Token"] = token
    return client.post(path, headers=h, **kw)


def test_unauthenticated_is_401_everywhere(env):
    _, c, *_ = env
    for m, u in [("get", "/own"), ("post", "/own"), ("get", "/any"), ("post", "/any")]:
        assert getattr(c, m)(u).status_code == 401


def test_session_get_needs_no_csrf_and_post_needs_all_checks(env):
    auth, c, *_ = env
    sid = login(auth, c)
    assert c.get("/own").json()["id"] == "owner"
    assert post(c, auth, sid).status_code == 200
    assert post(c, auth, sid, origin=None).status_code == 403          # no Origin: refuse
    assert post(c, auth, sid, origin="https://evil.example").status_code == 403
    assert post(c, auth, sid, csrf=None).status_code == 403            # no header
    assert post(c, auth, sid, csrf="deadbeef").status_code == 403      # header != cookie
    c.cookies.set(CSRF_COOKIE, "forged")
    assert post(c, auth, sid, csrf="forged").status_code == 403        # header == cookie but not derived
    c.cookies.set(CSRF_COOKIE, auth.csrf_token(sid))
    assert c.put("/own", headers={"Origin": ORIGIN}).status_code in (403, 405)


def test_origin_match_is_exact_not_prefix(env):
    auth, c, *_ = env
    sid = login(auth, c)
    for bad in (ORIGIN + ".evil.test", "http://worlds.example.test", ORIGIN + ":444", "null"):
        assert post(c, auth, sid, origin=bad).status_code == 403
    assert post(c, auth, sid, origin=ORIGIN + "/").status_code == 200  # trailing slash tolerated


def test_csrf_token_is_bound_to_the_session(env):
    auth, c, *_ = env
    sid1 = login(auth, c)
    other = auth.sessions.create()
    c.cookies.set(CSRF_COOKIE, auth.csrf_token(other))
    assert post(c, auth, sid1, csrf=auth.csrf_token(other)).status_code == 403


def test_only_hashes_are_stored(env):
    auth, c, _, tmp = env
    sid = login(auth, c)
    tid, token = auth.tokens.create("agent", ["memory.*"])
    raw = (tmp / "worlds.db").read_bytes() + b"".join(p.read_bytes() for p in tmp.glob("worlds.db-*"))
    assert sid.encode() not in raw and token.encode() not in raw


def test_session_expiry_idle_and_absolute(env):
    auth, c, clock, _ = env
    login(auth, c)
    assert c.get("/own").status_code == 200
    clock.t += IDLE_SECONDS + 1
    assert c.get("/own").status_code == 401
    login(auth, c)
    for _ in range(int(ABSOLUTE_SECONDS // 3600) + 2):  # keep it active, absolute cap still applies
        clock.t += 3600
        c.get("/own")
    assert c.get("/own").status_code == 401


def test_logout_and_garbage_cookies(env):
    auth, c, *_ = env
    sid = login(auth, c)
    auth.sessions.invalidate(sid)
    assert c.get("/own").status_code == 401
    for junk in ("", "x" * 500, "../../etc", "a b"):
        c.cookies.set(SESSION_COOKIE, junk)
        assert c.get("/own").status_code == 401


def test_agent_token_scopes_and_owner_only_routes(env):
    auth, c, *_ = env
    _, token = auth.tokens.create("a", ["memory.*", "deploy.status"])
    h = {"Authorization": f"Bearer {token}"}
    assert c.get("/own", headers=h).status_code == 403            # owner-only route
    r = c.get("/any", headers=h).json()
    assert r["kind"] == "agent" and r["scopes"] == ["deploy.status", "memory.*"]
    assert c.post("/any", headers=h).status_code == 200            # bearer needs no CSRF/Origin
    p = Principal("agent", "t", ("memory.*", "deploy.status"))
    assert p.allows_scope("memory.later.count") and p.allows_scope("deploy.status")
    assert not p.allows_scope("deploy.run") and not p.allows_scope("memory") and not p.allows_scope("memoryx.a")
    assert Principal("owner", "o").allows_scope("anything")


def test_bad_tokens_never_authenticate_and_never_fall_back_to_cookie(env):
    auth, c, clock, _ = env
    tid, token = auth.tokens.create("a", ["x"], ttl_s=60)
    login(auth, c)
    cases = [token + "x", token[:-3], "pwa_" + tid + "_wrong", "pwa_unknown_" + token.split("_", 2)[2], "", "nope",
             token.replace("pwa_", "pwb_")]
    for t in cases:
        assert c.get("/any", headers={"Authorization": f"Bearer {t}"}).status_code == 401, t   # valid cookie ignored
    assert c.get("/any", headers={"Authorization": f"Basic {token}"}).status_code == 401
    clock.t += 61
    assert c.get("/any", headers={"Authorization": f"Bearer {token}"}).status_code == 401      # expired
    tid2, t2 = auth.tokens.create("b", ["x"])
    assert auth.tokens.revoke(tid2) and not auth.tokens.revoke(tid2)
    assert c.get("/any", headers={"Authorization": f"Bearer {t2}"}).status_code == 401         # revoked


def test_a_token_is_never_step_up(env):
    auth, c, *_ = env
    _, token = auth.tokens.create("a", ["x"])
    p = auth.tokens.verify(token)
    assert not p.has_step_up(0) and not Principal("agent", "a", step_up_at=1.0, via="token").has_step_up(2.0)


def test_step_up_window(env):
    auth, c, clock, _ = env
    sid = login(auth, c)
    assert c.get("/own").json()["step_up"] is False
    assert auth.sessions.mark_step_up(sid)
    assert c.get("/own").json()["step_up"] is True
    clock.t += 299
    assert c.get("/own").json()["step_up"] is True
    clock.t += 5
    assert c.get("/own").json()["step_up"] is False
    assert not auth.sessions.mark_step_up("not-a-session")


def test_fails_closed_when_the_store_breaks(env, monkeypatch):
    auth, c, *_ = env
    login(auth, c)
    monkeypatch.setattr(auth.sessions, "get", lambda sid: (_ for _ in ()).throw(RuntimeError("db down")))
    assert c.get("/own").status_code == 401
    _, token = auth.tokens.create("a", ["x"])
    monkeypatch.setattr(auth.tokens, "verify", lambda t: (_ for _ in ()).throw(RuntimeError("db down")))
    assert c.get("/any", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_csrf_key_persisted_private(tmp_path):
    k1 = load_csrf_key(tmp_path)
    assert load_csrf_key(tmp_path) == k1 and len(k1) == 32
    assert not stat.S_IMODE((tmp_path / "csrf.key").stat().st_mode) & 0o077


def test_no_dev_bypass_symbols():
    import personal_world.worlds.authn as a
    src = open(a.__file__).read().lower()
    for word in ("testclient", "dev_bypass", "no_auth", "skip_auth"):
        assert word not in src


def test_database_files_and_directory_are_private(tmp_path):
    import os
    d = tmp_path / "data"
    d.mkdir(mode=0o755)
    os.chmod(d, 0o755)                                   # an existing, too-open data directory
    db = Database.in_dir(d)
    with db.write_tx() as tx:
        tx.execute("create table t(x)")
        tx.execute("insert into t values (1)")
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    names = [p.name for p in d.iterdir() if p.name.startswith("worlds.db")]
    assert "worlds.db" in names
    for n in names:
        assert not stat.S_IMODE((d / n).stat().st_mode) & 0o077, n


def test_key_creation_is_race_free_private_and_leaves_no_temp_files(tmp_path):
    import threading
    out = []
    ts = [threading.Thread(target=lambda: out.append(load_key(tmp_path / "d", "oidc-flow.key"))) for _ in range(24)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(out) == 24 and len({bytes(k) for k in out}) == 1 and len(out[0]) == 32     # everyone agrees
    f = tmp_path / "d" / "oidc-flow.key"
    assert f.read_bytes() == out[0] and not stat.S_IMODE(f.stat().st_mode) & 0o077
    assert sorted(p.name for p in (tmp_path / "d").iterdir()) == ["oidc-flow.key"]        # no .tmp/.new litter


def test_key_creation_across_processes(tmp_path):
    import subprocess
    import sys
    code = ("import sys; from personal_world.worlds.authn import load_key; "
            "sys.stdout.write(load_key(sys.argv[1], 'csrf.key').hex())")
    procs = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path / "x")], stdout=subprocess.PIPE) for _ in range(8)]
    keys = {p.communicate()[0] for p in procs}
    assert len(keys) == 1 and len(next(iter(keys))) == 64
    assert sorted(p.name for p in (tmp_path / "x").iterdir()) == ["csrf.key"]


def test_key_never_exposes_a_partial_file_and_a_short_existing_file_is_not_a_key(tmp_path):
    d = tmp_path / "k"
    d.mkdir()
    (d / "csrf.key").write_bytes(b"short")
    with pytest.raises(RuntimeError):
        load_key(d, "csrf.key")                              # never silently replaced: that would end every session
    (d / "csrf.key").write_bytes(b"\x01" * 32)
    assert load_key(d, "csrf.key") == b"\x01" * 32


def test_key_falls_back_to_exclusive_create_when_hard_links_are_unavailable(tmp_path, monkeypatch):
    def nolink(src, dst, **kw):
        raise OSError("hard links not supported")
    monkeypatch.setattr(os, "link", nolink)
    key = load_key(tmp_path / "nl", "csrf.key")
    assert len(key) == 32 and load_key(tmp_path / "nl", "csrf.key") == key
    assert sorted(p.name for p in (tmp_path / "nl").iterdir()) == ["csrf.key"]
