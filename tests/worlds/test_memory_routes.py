"""Memory routes through the production app: owner-only, step-up for locked, scoped agent counts, export/backup."""
import json
import stat
import time

import pytest
import yaml
from fastapi.testclient import TestClient

from personal_world.worlds.authn import SESSION_COOKIE
from personal_world.worlds.production import create_app

ORIGIN = "https://worlds.example.test"
BOOT = "open-sesame-correct-horse-1"  # pw-safety: synthetic


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    (cfg / "owner.yaml").write_text(yaml.safe_dump({"schema_version": 1, "public_origin": ORIGIN,
                                                    "bootstrap": {"enabled": True, "secret_ref": "env:PW_TEST_BOOTSTRAP"}}))
    app = create_app(cfg, data, maintenance_interval=3600)
    c = TestClient(app, base_url=ORIGIN, follow_redirects=False)
    return app, c, data


def login(app, c):
    assert c.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN}).status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": app.state.auth.csrf_token(c.cookies.get(SESSION_COOKIE))}


def step_up(c, h):
    assert c.post("/api/auth/step-up", json={"token": BOOT}, headers=h).status_code == 200


def token(app, c, h, scopes):
    r = c.post("/api/agent-tokens", json={"name": "bot", "scopes": scopes}, headers=h)
    return {"Authorization": f"Bearer {r.json()['token']}"}


ALL_GET = ["/api/memory/kept", "/api/memory/later", "/api/memory/records", "/api/memory/kept/x", "/api/memory/find?q=a",
           "/api/memory/history", "/api/memory/export/kept", "/api/memory/agent/later.count"]


def test_everything_needs_a_session_and_writes_need_csrf(env):
    app, c, _ = env
    for u in ALL_GET:
        assert c.get(u).status_code == 401, u
    for m, u in [("post", "/api/memory/kept"), ("patch", "/api/memory/kept/x"), ("delete", "/api/memory/kept/x"),
                 ("post", "/api/memory/backup")]:
        assert c.request(m.upper(), u, json={}).status_code == 401, u
    login(app, c)
    for m, u in [("post", "/api/memory/kept"), ("patch", "/api/memory/kept/x"), ("delete", "/api/memory/kept/x"),
                 ("post", "/api/memory/backup")]:
        assert c.request(m.upper(), u, json={"title": "t"}).status_code == 403, u               # session but no Origin/CSRF
        assert c.request(m.upper(), u, json={"title": "t"}, headers={"Origin": ORIGIN}).status_code == 403, u


def test_agent_tokens_cannot_use_owner_memory_routes(env):
    app, c, _ = env
    h = login(app, c)
    a = token(app, c, h, ["memory.*"])
    agent = TestClient(app, base_url=ORIGIN)
    for u in ALL_GET[:-1]:
        assert agent.get(u, headers=a).status_code == 403, u
    for m, u in [("post", "/api/memory/kept"), ("patch", "/api/memory/kept/x"), ("delete", "/api/memory/kept/x"),
                 ("post", "/api/memory/backup")]:
        assert agent.request(m.upper(), u, json={"title": "t"}, headers=a).status_code == 403, u


def test_owner_crud_flow(env):
    app, c, _ = env
    h = login(app, c)
    r = c.post("/api/memory/kept", json={"title": "Soup", "body": "lentils", "tags": ["food"]}, headers=h)
    assert r.status_code == 200 and r.json()["provenance"] == "owner"
    rid = r.json()["id"]
    assert c.get(f"/api/memory/kept/{rid}").json()["body"] == "lentils"
    assert c.patch(f"/api/memory/kept/{rid}", json={"title": "Better soup", "tags": ["food", "dinner"]}, headers=h).json()["tags"] == ["food", "dinner"]
    assert c.get("/api/memory/find?q=lentils").json()[0]["id"] == rid
    later = c.post("/api/memory/later", json={"title": "Call vet", "due_at": time.time() + 99}, headers=h).json()
    assert c.patch(f"/api/memory/later/{later['id']}", json={"status": "done"}, headers=h).json()["status"] == "done"
    assert [x["id"] for x in c.get("/api/memory/later?status=done").json()] == [later["id"]]
    assert c.delete(f"/api/memory/kept/{rid}", headers=h).json() == {"ok": True}
    assert c.get(f"/api/memory/kept/{rid}").status_code == 404
    ev = [e["event"] for e in c.get("/api/memory/history").json()]
    assert ev[:2] == ["deleted", "updated"] or "deleted" in ev


def test_validation_is_400_not_500_and_never_a_traceback(env):
    app, c, _ = env
    h = login(app, c)
    for body in ({}, {"title": ""}, {"title": "x" * 300}, {"title": "t", "bogus": 1}, {"title": "t", "status": "open"},
                 {"title": "t", "provenance": "external_ref"}, {"title": "t", "tags": "nope"}):
        r = c.post("/api/memory/kept", json=body, headers=h)
        assert r.status_code == 400 and "Traceback" not in r.text, body
    assert c.get("/api/memory/nope").status_code == 400
    assert c.get("/api/memory/kept?limit=0").status_code == 400
    assert c.get("/api/memory/find?q=a&limit=1000").status_code == 400
    assert c.patch("/api/memory/kept/zzz", json={"title": "x"}, headers=h).status_code == 404
    assert c.patch("/api/memory/kept/zzz", json={}, headers=h).status_code == 400


def test_duplicate_id_is_400_not_500(env, monkeypatch):
    app, c, _ = env
    h = login(app, c)

    class _FixedUUID:                                          # every add now mints the same id
        class _Uuid:
            hex = "0" * 32

        @staticmethod
        def uuid4():
            return _FixedUUID._Uuid()

    monkeypatch.setattr("personal_world.worlds.memory_store.uuid", _FixedUUID)
    assert c.post("/api/memory/kept", json={"title": "first"}, headers=h).status_code == 200
    before = {t: app.state.db.conn().execute(f"select count(*) from {t}").fetchone()[0]
              for t in ("kept", "find_index", "history")}
    r = c.post("/api/memory/kept", json={"title": "duplicate"}, headers=h)
    assert r.status_code == 400 and "Traceback" not in r.text   # a duplicate id is a 400, never a 500
    assert isinstance(r.json().get("detail"), str) and "kept" in r.json()["detail"] and "duplicate" in r.json()["detail"]
    for table, n in before.items():                             # the refused insert left nothing behind
        assert app.state.db.conn().execute(f"select count(*) from {table}").fetchone()[0] == n, table


def test_locked_records_need_session_step_up_on_every_route(env):
    app, c, _ = env
    h = login(app, c)
    rec = c.post("/api/memory/records", json={"title": "Heron", "body": "blue heron", "sensitivity": "locked"}, headers=h).json()
    rid = rec["id"]
    r = c.get(f"/api/memory/records/{rid}")
    assert r.status_code == 403 and r.json()["detail"] == "step_up_required"
    assert c.patch(f"/api/memory/records/{rid}", json={"body": "x"}, headers=h).status_code == 403
    assert c.delete(f"/api/memory/records/{rid}", headers=h).status_code == 403
    listed = c.get("/api/memory/records").json()
    assert listed == [{"id": rid, "table": "records", "sensitivity": "locked", "locked": True, "created_at": listed[0]["created_at"]}]
    assert c.get("/api/memory/find?q=heron").json() == []
    assert "heron" not in c.get("/api/memory/export/records").text.lower()
    step_up(c, h)
    assert c.get(f"/api/memory/records/{rid}").json()["body"] == "blue heron"
    assert c.get("/api/memory/find?q=heron").json()[0]["id"] == rid
    assert c.get("/api/memory/records").json()[0]["title"] == "Heron"
    assert "heron" in c.get("/api/memory/export/records").text.lower()
    assert c.patch(f"/api/memory/records/{rid}", json={"sensitivity": "normal"}, headers=h).status_code == 200


def test_step_up_expires_and_a_token_never_has_it(env):
    app, c, _ = env
    h = login(app, c)
    rid = c.post("/api/memory/records", json={"title": "L", "sensitivity": "locked"}, headers=h).json()["id"]
    step_up(c, h)
    assert c.get(f"/api/memory/records/{rid}").status_code == 200
    c.cookies.get(SESSION_COOKIE)
    with app.state.db.write_tx() as tx:                                    # five minutes and a bit later
        tx.execute("update sessions set step_up_at = step_up_at - 400")
    assert c.get(f"/api/memory/records/{rid}").status_code == 403
    a = token(app, c, h, ["memory.*", "*"])
    agent = TestClient(app, base_url=ORIGIN)
    assert agent.get(f"/api/memory/records/{rid}", headers=a).status_code == 403


def test_agent_counts_are_scoped_logged_and_content_free(env):
    app, c, _ = env
    h = login(app, c)
    c.post("/api/memory/later", json={"title": "secret plan"}, headers=h)
    c.post("/api/memory/records", json={"title": "locked", "sensitivity": "locked"}, headers=h)
    narrow = token(app, c, h, ["memory.later.count"])
    wide = token(app, c, h, ["memory.*"])
    other = token(app, c, h, ["deploy.*"])
    a = TestClient(app, base_url=ORIGIN)
    assert a.get("/api/memory/agent/later.count", headers=narrow).json() == {"name": "later.count", "value": 1}
    assert a.get("/api/memory/agent/kept.count", headers=narrow).status_code == 403
    assert a.get("/api/memory/agent/records.count", headers=wide).json()["value"] == 0          # locked is not counted
    assert a.get("/api/memory/agent/later.count", headers=other).status_code == 403
    assert a.get("/api/memory/agent/search", headers=wide).status_code == 404                   # no generic search
    assert a.get("/api/memory/agent/later.titles", headers=wide).status_code == 404
    assert "secret plan" not in a.get("/api/memory/agent/later.count", headers=wide).text
    events = [(e["event"], e["actor"]) for e in c.get("/api/memory/history").json() if e["event"] == "agent_read"]
    assert len(events) >= 3
    assert c.get("/api/memory/agent/later.count").json()["value"] == 1                            # the owner may ask too


def test_export_streams_ndjson_and_is_logged(env):
    app, c, _ = env
    h = login(app, c)
    c.post("/api/memory/kept", json={"title": "a"}, headers=h)
    c.post("/api/memory/kept", json={"title": "b"}, headers=h)
    r = c.get("/api/memory/export/kept")
    assert r.headers["content-type"].startswith("application/x-ndjson") and "attachment" in r.headers["content-disposition"]
    assert [json.loads(x)["title"] for x in r.text.splitlines()] == ["a", "b"] or len(r.text.splitlines()) == 2
    assert c.get("/api/memory/export/sqlite_master").status_code == 400
    assert c.get("/api/memory/export/history").status_code == 200
    assert any(e["event"] == "exported" for e in c.get("/api/memory/history").json())


def test_backup_endpoint_makes_a_private_dated_file(env):
    app, c, data = env
    h = login(app, c)
    c.post("/api/memory/kept", json={"title": "a"}, headers=h)
    r = c.post("/api/memory/backup", headers=h)
    assert r.status_code == 200 and r.json()["file"].startswith("worlds-") and "/" not in r.json()["file"]
    f = data / "backups" / r.json()["file"]
    assert f.is_file() and not stat.S_IMODE(f.stat().st_mode) & 0o077
    assert not stat.S_IMODE((data / "backups").stat().st_mode) & 0o077
    assert any(e["event"] == "backup" and e["detail"] == {"file": r.json()["file"]} for e in c.get("/api/memory/history").json())


def test_find_is_never_syntax_over_http(env):
    app, c, _ = env
    h = login(app, c)
    c.post("/api/memory/kept", json={"title": "foo bar"}, headers=h)
    for q in ['foo"bar', "NEAR(a b)", "title:foo", "'; DROP TABLE kept;--", "*", "(foo", "foo OR"]:
        assert c.get("/api/memory/find", params={"q": q}).status_code == 200, q
    assert len(c.get("/api/memory/kept").json()) == 1
