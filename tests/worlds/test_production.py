"""End-to-end through the production app: real confinement, real sessions, real dispatcher."""
import json
import time

import pytest
import yaml
from fastapi.testclient import TestClient

from personal_world.worlds import confinement
from personal_world.worlds.authn import CSRF_COOKIE, SESSION_COOKIE
from personal_world.worlds.config_store import ConfigStore
from personal_world.worlds.models import Action, Provider, Request
from personal_world.worlds.production import create_app
from personal_world.worlds.reference_provider import ReferenceServer

ORIGIN = "https://worlds.example.test"
BOOT = "open-sesame-correct-horse-1"  # pw-safety: synthetic


@pytest.fixture
def ref():
    with ReferenceServer(token="t") as s:
        yield s


def write_owner(cfg):
    (cfg / "owner.yaml").write_text(yaml.safe_dump({
        "schema_version": 1, "public_origin": ORIGIN,
        "bootstrap": {"enabled": True, "secret_ref": "env:PW_TEST_BOOTSTRAP"}}))


def seed(cfg, ref):
    s = ConfigStore(cfg)
    s.save("provider", Provider(id="svc", name="Svc", kind="http", base_url=ref.base_url, network={"lan": True}))
    s.save("request", Request(id="svc.ping", provider="svc", method="POST", path="/actions/ping"))
    s.save("request", Request(id="svc.lost", provider="svc", method="POST", path="/lost"))
    s.save("request", Request(id="svc.items", provider="svc", path="/items"))
    s.save("action", Action(id="ping", request="svc.ping", name="Ping", scope="deploy.run", exposed=True, idempotency="optional"))
    s.save("action", Action(id="lost", request="svc.lost", name="Lost", scope="deploy.run", exposed=True))
    s.save("action", Action(id="secret-op", request="svc.ping", name="Hidden", scope="deploy.run", exposed=False))
    s.save("action", Action(id="peek", request="svc.items", name="Peek", access="read", approval="never", scope="deploy.read", exposed=True))


@pytest.fixture
def env(tmp_path, monkeypatch, ref):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    write_owner(cfg)
    seed(cfg, ref)
    app = create_app(cfg, data)
    c = TestClient(app, base_url=ORIGIN, follow_redirects=False)
    return app, c, cfg, data


def owner_headers(app, c):
    sid = c.cookies.get(SESSION_COOKIE)
    return {"Origin": ORIGIN, "X-CSRF-Token": app.state.auth.csrf_token(sid)}


def login(app, c):
    r = c.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN})
    assert r.status_code == 200
    return owner_headers(app, c)


def step_up(app, c, h):
    assert c.post("/api/auth/step-up", json={"token": BOOT}, headers=h).status_code == 200


def make_token(app, c, h, scopes=("deploy.*",)):
    r = c.post("/api/agent-tokens", json={"name": "bot", "scopes": list(scopes)}, headers=h)
    assert r.status_code == 200
    return r.json()


def agent_h(token):
    return {"Authorization": f"Bearer {token}"}


def test_production_has_no_override_and_wires_confinement(env):
    app, *_ = env
    assert app.state.runner._send is confinement.confined_request
    assert app.state.dispatcher._send is confinement.confined_request


def test_everything_requires_auth_but_healthz_and_session(env):
    app, c, *_ = env
    assert c.get("/healthz").status_code == 200
    assert c.get("/api/auth/session").json()["authenticated"] is False
    for m, u in [("get", "/api/boards/home"), ("get", "/api/cards/x"), ("get", "/api/needs-you"), ("get", "/api/actions"),
                 ("post", "/api/actions/ping/authorizations"), ("get", "/api/receipts"), ("post", "/api/agent-tokens"),
                 ("get", "/api/agent-tokens"), ("get", "/api/config/provider"), ("post", "/api/authorizations/x/approve")]:
        assert getattr(c, m)(u).status_code in (401, 403), u


def test_host_header_is_enforced(env):
    app, c, *_ = env
    assert c.get("/healthz", headers={"Host": "evil.example"}).status_code == 400


def test_full_flow_agent_asks_owner_approves_agent_runs_once_over_the_real_network(env, ref):
    app, c, *_ = env
    h = login(app, c)
    tok = make_token(app, c, h)
    assert "token" in tok and "pwa_" in tok["token"]
    listed = c.get("/api/agent-tokens").json()
    assert "token" not in json.dumps(listed) and tok["token"] not in json.dumps(listed)

    agent = TestClient(app, base_url=ORIGIN)               # no cookies: a token caller
    names = {a["id"] for a in agent.get("/api/actions", headers=agent_h(tok["token"])).json()}
    assert names == {"ping", "lost", "peek"}               # secret-op is not exposed
    assert agent.post("/api/actions/secret-op/authorizations", headers=agent_h(tok["token"])).status_code == 403

    r = agent.post("/api/actions/ping/authorizations", json={"idempotency_key": "k-1"}, headers=agent_h(tok["token"]))
    assert r.status_code == 200 and r.json()["state"] == "pending"
    aid = r.json()["id"]
    needs = c.get("/api/needs-you").json()
    assert needs[0]["action"] == {"kind": "approve", "authorization_id": aid} and needs[0]["source"] == "actions"

    assert agent.post(f"/api/authorizations/{aid}/approve", headers=agent_h(tok["token"])).status_code == 403   # a token never approves
    assert c.post(f"/api/authorizations/{aid}/approve", headers=h).status_code == 403                           # no step-up yet
    assert agent.post(f"/api/authorizations/{aid}/execute", headers=agent_h(tok["token"])).status_code == 409   # not approved
    assert ref.counters.get("ping", 0) == 0

    step_up(app, c, h)
    ok = c.post(f"/api/authorizations/{aid}/approve", headers=h)
    assert ok.status_code == 200 and ok.json()["authority"] == "worlds_owner" and ok.json()["state"] == "approved"
    assert c.get("/api/needs-you").json() == []

    run = agent.post(f"/api/authorizations/{aid}/execute", headers=agent_h(tok["token"]))
    assert run.status_code == 200 and run.json()["state"] == "SUCCEEDED" and run.json()["status_code"] == 200
    assert ref.counters["ping"] == 1
    assert agent.post(f"/api/authorizations/{aid}/execute", headers=agent_h(tok["token"])).status_code == 409
    assert ref.counters["ping"] == 1
    sent = [call for call in ref.calls if call[1] == "/actions/ping"]
    assert len(sent) == 1 and {k.lower(): v for k, v in sent[0][2].items()}.get("idempotency-key") == "k-1"


def test_owner_writes_need_csrf_and_origin(env):
    app, c, *_ = env
    h = login(app, c)
    assert c.post("/api/agent-tokens", json={"name": "b", "scopes": ["x"]}).status_code == 403
    assert c.post("/api/agent-tokens", json={"name": "b", "scopes": ["x"]}, headers={"Origin": ORIGIN}).status_code == 403
    bad = dict(h, Origin="https://evil.example")
    assert c.post("/api/agent-tokens", json={"name": "b", "scopes": ["x"]}, headers=bad).status_code == 403
    assert c.post("/api/agent-tokens", json={"name": "b", "scopes": ["x"]}, headers=h).status_code == 200


def test_token_validation_and_revocation(env):
    app, c, *_ = env
    h = login(app, c)
    for body in ({}, {"name": "x"}, {"name": "x", "scopes": []}, {"name": "x", "scopes": [1]}, {"name": "", "scopes": ["a"]},
                 {"name": "x", "scopes": ["a"], "ttl_s": 5}, {"name": "x", "scopes": ["a"], "ttl_s": True}):
        assert c.post("/api/agent-tokens", json=body, headers=h).status_code == 400, body
    tok = make_token(app, c, h)
    a = TestClient(app, base_url=ORIGIN)
    assert a.get("/api/actions", headers=agent_h(tok["token"])).status_code == 200
    assert a.get("/api/agent-tokens", headers=agent_h(tok["token"])).status_code == 403     # owner only
    assert a.post("/api/agent-tokens", json={"name": "z", "scopes": ["*"]}, headers=agent_h(tok["token"])).status_code == 403
    assert c.delete(f"/api/agent-tokens/{tok['id']}", headers=h).status_code == 200
    assert a.get("/api/actions", headers=agent_h(tok["token"])).status_code == 401
    assert c.delete(f"/api/agent-tokens/{tok['id']}", headers=h).status_code == 404


def test_agent_scope_limits_what_it_can_request_and_see(env):
    app, c, *_ = env
    h = login(app, c)
    tok = make_token(app, c, h, scopes=("deploy.read",))
    a = TestClient(app, base_url=ORIGIN)
    assert {x["id"] for x in a.get("/api/actions", headers=agent_h(tok["token"])).json()} == {"peek"}
    assert a.post("/api/actions/ping/authorizations", headers=agent_h(tok["token"])).status_code == 403
    r = a.post("/api/actions/peek/authorizations", headers=agent_h(tok["token"]))
    assert r.json()["state"] == "approved"                                                      # approval: never, read effect
    run = a.post(f"/api/authorizations/{r.json()['id']}/execute", headers=agent_h(tok["token"]))
    assert run.json()["state"] == "SUCCEEDED"


def test_authorizations_and_receipts_are_private_to_the_caller(env):
    app, c, *_ = env
    h = login(app, c)
    t1, t2 = make_token(app, c, h)["token"], make_token(app, c, h)["token"]
    a = TestClient(app, base_url=ORIGIN)
    aid = a.post("/api/actions/peek/authorizations", headers=agent_h(t1)).json()["id"]
    assert a.get(f"/api/authorizations/{aid}", headers=agent_h(t2)).status_code == 404
    assert a.post(f"/api/authorizations/{aid}/execute", headers=agent_h(t2)).status_code == 403
    ex = a.post(f"/api/authorizations/{aid}/execute", headers=agent_h(t1)).json()
    assert a.get(f"/api/receipts/{ex['execution_id']}", headers=agent_h(t2)).status_code == 404
    mine = a.get(f"/api/receipts/{ex['execution_id']}", headers=agent_h(t1)).json()
    assert set(mine["evidence"]) <= {"error_class", "status_code"} and "destination" not in mine   # no topology to agents
    assert a.get("/api/receipts", headers=agent_h(t1)).status_code == 403
    full = c.get("/api/receipts").json()
    assert full[0]["execution_id"] == ex["execution_id"] and "destination" in full[0]


def test_unknown_outcome_then_retry_needs_a_new_approval(env, ref):
    app, c, *_ = env
    h = login(app, c)
    step_up(app, c, h)
    aid = c.post("/api/actions/lost/authorizations", json={}, headers=h).json()["id"]
    c.post(f"/api/authorizations/{aid}/approve", headers=h)
    ex = c.post(f"/api/authorizations/{aid}/execute", headers=h).json()
    assert ex["state"] == "UNKNOWN" and ref.counters["lost"] == 1
    assert c.post(f"/api/authorizations/{aid}/execute", headers=h).status_code == 409
    retry = c.post(f"/api/executions/{ex['execution_id']}/retry", headers=h).json()
    assert retry["state"] == "pending" and retry["previous_may_have_run"] is True and retry["retry_of"] == ex["execution_id"]
    assert ref.counters["lost"] == 1                          # nothing was re-sent automatically


def test_config_change_invalidates_a_pending_authorization_end_to_end(env, ref):
    app, c, *_ = env
    h = login(app, c)
    step_up(app, c, h)
    aid = c.post("/api/actions/ping/authorizations", json={}, headers=h).json()["id"]
    p = c.get("/api/config/request/svc.ping")
    body = p.json() | {"path": "/actions/other"}
    assert c.put("/api/config/request/svc.ping", json=body, headers={**h, "If-Match": p.headers["etag"]}).status_code == 200
    assert c.post(f"/api/authorizations/{aid}/approve", headers=h).status_code == 409
    assert c.get(f"/api/authorizations/{aid}").json()["state"] == "invalidated"
    assert ref.counters.get("ping", 0) == 0


def test_startup_recovery_marks_interrupted_executions_unknown(tmp_path, monkeypatch, ref):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    write_owner(cfg)
    seed(cfg, ref)
    app = create_app(cfg, data, maintenance_interval=3600)
    d = app.state.dispatcher
    from personal_world.worlds.authn import Principal
    o = Principal("owner", "owner", step_up_at=time.time(), via="session")
    a = d.approve(o, d.request_authorization(o, "ping")["id"])
    d._consume(o, a["id"])                               # the process "dies" here
    with app.state.db.write_tx() as tx:                  # the dead process's lease lapses
        tx.execute("update leases set heartbeat = heartbeat - 1000")
    app.state.db.close()
    again = create_app(cfg, data)
    assert again.state.recovered == 1
    assert again.state.dispatcher.list_receipts()[0]["state"] == "UNKNOWN" and ref.counters.get("ping", 0) == 0


def test_fails_closed_without_a_valid_owner_policy(tmp_path, ref):
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    seed(cfg, ref)
    app = create_app(cfg, data)                               # no owner.yaml
    c = TestClient(app, base_url=ORIGIN)
    assert c.get("/healthz", headers={"Host": "worlds.example.test"}).status_code == 400   # no allowed host at all
    sid = app.state.auth.sessions.create()                    # even a valid-looking session cannot write: no allowed origin
    c2 = TestClient(app, base_url="http://invalid.invalid")
    c2.cookies.set(SESSION_COOKIE, sid)
    c2.cookies.set(CSRF_COOKIE, app.state.auth.csrf_token(sid))
    r = c2.post("/api/agent-tokens", json={"name": "b", "scopes": ["x"]},
                headers={"Origin": ORIGIN, "X-CSRF-Token": app.state.auth.csrf_token(sid)})
    assert r.status_code == 403
    assert c2.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN}).status_code == 403


def test_recovery_has_already_run_before_the_first_request(tmp_path, monkeypatch, ref):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    write_owner(cfg)
    seed(cfg, ref)
    first = create_app(cfg, data, maintenance_interval=3600)
    d = first.state.dispatcher
    from personal_world.worlds.authn import Principal
    o = Principal("owner", "owner", step_up_at=time.time(), via="session")
    d._consume(o, d.approve(o, d.request_authorization(o, "ping")["id"])["id"])
    with first.state.db.write_tx() as tx:
        tx.execute("update leases set heartbeat = heartbeat - 1000")
    first.state.db.close()
    second = create_app(cfg, data, maintenance_interval=3600)
    c = TestClient(second, base_url=ORIGIN, follow_redirects=False)
    login(second, c)
    assert c.get("/api/receipts").json()[0]["state"] == "UNKNOWN"      # already settled when the first request lands


def test_a_live_process_is_not_recovered_out_from_under_itself(tmp_path, monkeypatch, ref):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    write_owner(cfg)
    seed(cfg, ref)
    live = create_app(cfg, data, maintenance_interval=3600)
    from personal_world.worlds.authn import Principal
    o = Principal("owner", "owner", step_up_at=time.time(), via="session")
    d = live.state.dispatcher
    d._consume(o, d.approve(o, d.request_authorization(o, "ping")["id"])["id"])     # in flight in a LIVE process
    second = create_app(cfg, data, maintenance_interval=3600)                         # a second process starts
    assert second.state.recovered == 0
    assert live.state.db.conn().execute("select state from executions").fetchone()[0] == "INTENT"


def test_new_app_does_not_use_the_old_auth_stack():
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-c",
                          "import sys, personal_world.worlds.production as p; "
                          "print([m for m in ('personal_world.api','personal_world.auth','personal_world.auth_routes','personal_world.identity') if m in sys.modules])"],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]"


def test_app_from_env_requires_both_directories(monkeypatch, tmp_path):
    from personal_world.worlds.production import app_from_env
    monkeypatch.delenv("PW_CONFIG_DIR", raising=False)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    with pytest.raises(SystemExit):
        app_from_env()
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path / "cfg"))
    (tmp_path / "cfg").mkdir()
    assert app_from_env().title


def test_sessions_are_bound_to_the_owner_identity_in_production(env):
    app, c, cfg, data = env
    login(app, c)
    assert c.get("/api/auth/session").json()["authenticated"]
    (cfg / "owner.yaml").write_text(yaml.safe_dump({"schema_version": 1, "public_origin": ORIGIN, "bootstrap": {"enabled": True, "secret_ref": "env:PW_TEST_BOOTSTRAP"},
                                         "oidc": {"issuer": "https://auth.example.test", "subject": "new-owner"}}))
    assert c.get("/api/auth/session").json()["authenticated"] is False


# ------------------------------------------------------------- review #237 follow-up 5

def test_redaction_knows_every_provider_secret_without_being_told_and_follows_rotation(tmp_path, monkeypatch, ref):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    monkeypatch.setenv("SVC_TOKEN", "first-secret-value-1234")
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    write_owner(cfg)
    s = ConfigStore(cfg)
    s.save("provider", Provider(id="svc", name="Svc", kind="http", base_url=ref.base_url, network={"lan": True},
                                auth={"type": "bearer", "secret_ref": "env:SVC_TOKEN"}))
    s.save("request", Request(id="svc.items", provider="svc", path="/items", ttl_s=0))
    app = create_app(cfg, data, maintenance_interval=3600)                 # secret_values NOT passed
    runner = app.state.runner
    from personal_world.worlds.confinement import ConfinementError
    runner._send = lambda p, r, *, effect: ConfinementError("connection", "failed with first-secret-value-1234 inside")
    assert "first-secret-value-1234" not in runner.fetch("svc.items").note
    monkeypatch.setenv("SVC_TOKEN", "rotated-secret-value-9999")           # rotated after startup
    runner._send = lambda p, r, *, effect: ConfinementError("connection", "now rotated-secret-value-9999 leaked?")
    assert "rotated-secret-value-9999" not in runner.fetch("svc.items", force=True).note
    d = app.state.dispatcher
    from personal_world.worlds.authn import Principal
    app.state.store.save("request", Request(id="svc.go", provider="svc", method="POST", path="/go"))
    app.state.store.save("action", Action(id="go", request="svc.go", name="Go"))
    o = Principal("owner", "owner", step_up_at=time.time(), via="session")
    d._send = lambda p, r, *, effect: ConfinementError("timeout", "slow rotated-secret-value-9999 here")
    a = d.approve(o, d.request_authorization(o, "go")["id"])
    receipt = d.execute(o, a["id"])
    assert "rotated-secret-value-9999" not in json.dumps(receipt)


def test_oidc_flow_key_is_persisted_privately_and_shared(tmp_path, monkeypatch, ref):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    write_owner(cfg)
    create_app(cfg, data, maintenance_interval=3600)
    key = (data / "oidc-flow.key").read_bytes()
    assert len(key) == 32 and not (data / "oidc-flow.key").stat().st_mode & 0o077
    create_app(cfg, data, maintenance_interval=3600)
    assert (data / "oidc-flow.key").read_bytes() == key                       # a second worker/restart agrees


def test_app_from_env_reads_trusted_proxies_and_rejects_junk(monkeypatch, tmp_path):
    from personal_world.worlds.production import app_from_env
    (tmp_path / "cfg").mkdir()
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PW_TRUSTED_PROXIES", "192.0.2.10, 198.51.100.0/24")
    assert app_from_env().title
    monkeypatch.setenv("PW_TRUSTED_PROXIES", "192.0.2.10, nonsense")
    with pytest.raises(SystemExit):
        app_from_env()


def test_startup_fails_closed_on_a_weak_bootstrap_secret(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    write_owner(cfg)
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", "guessable-ish")
    with pytest.raises(SystemExit) as exc:
        create_app(cfg, tmp_path / "data", maintenance_interval=3600)
    assert "token_urlsafe(32)" in str(exc.value)
    monkeypatch.delenv("PW_TEST_BOOTSTRAP")
    assert create_app(cfg, tmp_path / "data2", maintenance_interval=3600).title     # unset: bootstrap is simply unusable
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", "a" * 32)
    assert create_app(cfg, tmp_path / "data3", maintenance_interval=3600).title
