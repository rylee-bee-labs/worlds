"""Connect workshop API: try (read only, through confinement, scrubbed, rate limited, audited) and preview."""
import json

import pytest
import yaml
from fastapi.testclient import TestClient

from personal_world.worlds.authn import SESSION_COOKIE
from personal_world.worlds.config_store import ConfigStore
from personal_world.worlds.mapping import extract, parse_path
from personal_world.worlds.models import Provider, Request
from personal_world.worlds.production import create_app
from personal_world.worlds.reference_provider import ReferenceServer
from personal_world.worlds.suggest import MAX_SUGGESTIONS, redact_sample, scrub_text, suggest_fields

ORIGIN = "https://worlds.example.test"
BOOT = "open-sesame-correct-horse-1"  # pw-safety: synthetic
TOKEN = "dev-ref-token-abcdefgh-0123456789"  # pw-safety: synthetic


@pytest.fixture
def ref():
    with ReferenceServer(token=TOKEN) as s:
        yield s


@pytest.fixture
def env(tmp_path, monkeypatch, ref):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    monkeypatch.setenv("CONNECT_REF_TOKEN", TOKEN)
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    (cfg / "owner.yaml").write_text(yaml.safe_dump({"schema_version": 1, "public_origin": ORIGIN,
                                                    "bootstrap": {"enabled": True, "secret_ref": "env:PW_TEST_BOOTSTRAP"}}))
    s = ConfigStore(cfg)
    s.save("provider", Provider(id="svc", name="Svc", kind="http", base_url=ref.base_url, network={"lan": True}))
    s.save("request", Request(id="svc.status", provider="svc", path="/status"))
    s.save("request", Request(id="svc.go", provider="svc", method="POST", path="/actions/ping"))
    app = create_app(cfg, data, maintenance_interval=3600)
    c = TestClient(app, base_url=ORIGIN, follow_redirects=False)
    assert c.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN}).status_code == 200
    h = {"Origin": ORIGIN, "X-CSRF-Token": app.state.auth.csrf_token(c.cookies.get(SESSION_COOKIE))}
    return app, c, h, ref


def try_(c, h, provider, request):
    return c.post("/api/connect/try", json={"provider": provider, "request": request}, headers=h)


def unsaved(ref, **kw):
    return {"kind": "http", "base_url": ref.base_url, "network": {"lan": True}, **kw}


# ---------------------------------------------------------------------- access

def test_owner_only_and_csrf(env):
    app, c, h, ref = env
    anon = TestClient(app, base_url=ORIGIN)
    for path, body in [("/api/connect/try", {"provider": "svc", "request": {"path": "/status"}}),
                       ("/api/connect/preview", {"card": {}, "sample": {}})]:
        assert anon.post(path, json=body).status_code == 401
        assert c.post(path, json=body).status_code == 403                       # session without Origin/CSRF
        assert c.post(path, json=body, headers={"Origin": ORIGIN}).status_code == 403
    tok = c.post("/api/agent-tokens", json={"name": "b", "scopes": ["*"]}, headers=h).json()["token"]
    assert anon.post("/api/connect/try", json={"provider": "svc", "request": {"path": "/status"}},
                     headers={"Authorization": f"Bearer {tok}"}).status_code == 403
    assert ref.calls == []


# ------------------------------------------------------------------------- try

def test_try_a_saved_provider_returns_a_sample_and_suggestions(env):
    app, c, h, ref = env
    r = try_(c, h, "svc", {"path": "/status"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["status_code"] == 200 and body["error_class"] is None and body["duration_ms"] is not None
    assert json.loads(body["sample"])["state"] == "ok" and body["truncated"] is False
    paths = {f["path"]: f for f in body["suggested_fields"]}
    assert paths["$.uptime"]["format"] == "duration" and paths["$.cpu"]["format"] == "percent" and paths["$.disk.used"]["format"] == "bytes"
    assert paths["$.state"]["sample"] == "ok"
    assert len([x for x in ref.calls if x[1] == "/status"]) == 1                 # exactly one network attempt
    assert r.headers["cache-control"] == "no-store"


def test_try_an_unsaved_provider_with_a_secret_ref_sends_the_credential_and_scrubs_the_echo(env):
    app, c, h, ref = env
    r = try_(c, h, unsaved(ref, auth={"type": "bearer", "secret_ref": "env:CONNECT_REF_TOKEN"}), {"path": "/secret-echo"})
    body = r.json()
    assert body["ok"] is True and TOKEN not in r.text and "Bearer" not in r.text          # the server echoed it; the sample hides it
    assert "[redacted]" in body["sample"]
    seen = [dict(x[2]) for x in ref.calls if x[1] == "/secret-echo"][0]
    assert {k.lower(): v for k, v in seen.items()}["authorization"] == f"Bearer {TOKEN}"   # but it was really sent


def test_an_unsaved_provider_cannot_borrow_worlds_own_secrets(env, monkeypatch):
    app, c, h, ref = env
    monkeypatch.setenv("PW_API_TOKEN", "x" * 40)
    for name in ("PW_API_TOKEN", "PW_TEST_BOOTSTRAP", "OIDC_CLIENT_SECRET", "SOMETHING_BOOTSTRAP_KEY"):
        r = try_(c, h, unsaved(ref, auth={"type": "bearer", "secret_ref": f"env:{name}"}), {"path": "/items"})
        assert r.status_code == 422 and "belongs to Worlds" in r.json()["detail"], name
    assert ref.calls == []


def test_a_raw_secret_can_never_be_supplied(env):
    app, c, h, ref = env
    for extra in ({"token": "abc"}, {"password": "p"}, {"auth": {"type": "bearer", "secret_ref": "abc"}},
                  {"auth": {"type": "bearer", "secret_ref": "env:X", "value": "raw"}}, {"api_key": "k"}):
        r = try_(c, h, unsaved(ref, **extra), {"path": "/items"})
        assert r.status_code == 422, extra
    assert ref.calls == []


def test_writes_are_refused_and_nothing_is_sent(env):
    app, c, h, ref = env
    for req in ({"path": "/actions/ping", "method": "POST"}, {"path": "/x", "method": "DELETE"}, {"path": "/x", "effect": "write"},
                {"path": "/x", "method": "POST", "effect": "read"}):
        r = try_(c, h, "svc", req)
        assert r.status_code == 422 and r.json()["detail"] == "test write actions through an approved action", req
    assert ref.calls == [] and ref.counters.get("ping", 0) == 0


def test_validation_errors_are_plain_422s(env):
    app, c, h, ref = env
    cases = [({"provider": "nope", "request": {"path": "/x"}}, 404), ({"provider": "svc"}, 422), ({"request": {"path": "/x"}}, 422),
             ({"provider": "svc", "request": {"path": "/x"}, "extra": 1}, 422), ({"provider": 5, "request": {"path": "/x"}}, 422),
             ({"provider": "svc", "request": {"path": "http://evil.test/x"}}, 422), ({"provider": "svc", "request": {"path": "/a/../b"}}, 422),
             ({"provider": "svc", "request": {"path": "/x", "headers": {"Authorization": "x"}}}, 422),
             ({"provider": {"base_url": "not a url"}, "request": {"path": "/x"}}, 422), ({"provider": "svc", "request": 7}, 422)]
    for body, code in cases:
        r = c.post("/api/connect/try", json=body, headers=h)
        assert r.status_code == code and "Traceback" not in r.text, body
    assert ref.calls == []


def test_try_goes_through_confinement(env):
    app, c, h, ref = env
    r = try_(c, h, {"kind": "http", "base_url": ref.base_url}, {"path": "/items"})        # lan not set: loopback is internal
    body = r.json()
    assert body["ok"] is False and body["error_class"] == "confinement_denied" and ref.calls == []
    meta = try_(c, h, {"kind": "http", "base_url": "http://169.254.169.254", "network": {"lan": True}}, {"path": "/latest"}).json()   # pw-safety: synthetic
    assert meta["error_class"] == "confinement_denied"


def test_errors_are_reported_not_hidden(env):
    app, c, h, ref = env
    boom = try_(c, h, "svc", {"path": "/boom"}).json()
    assert boom["ok"] is False and boom["status_code"] == 500 and boom["error_class"] == "http_5xx" and boom["suggested_fields"] == []
    assert try_(c, h, "svc", {"path": "/nothing-here"}).json()["error_class"] == "http_4xx"
    assert try_(c, h, "svc", {"path": "/secret"}).json()["error_class"] == "auth_failed"
    mal = try_(c, h, "svc", {"path": "/malformed"}).json()
    assert mal["ok"] is False and mal["error_class"] == "malformed" and "not json" in mal["sample"]
    slow = try_(c, h, "svc", {"path": "/slow", "query": {"delay": "3"}, "timeout_s": 0.3}).json()
    assert slow["error_class"] == "timeout"
    redir = try_(c, h, "svc", {"path": "/redirect"}).json()
    assert redir["error_class"] == "redirect_refused" and ref.calls_to("/items") == 0


def test_the_sample_is_capped_at_16_kb(env):
    app, c, h, ref = env
    big = try_(c, h, {"kind": "http", "base_url": ref.base_url, "network": {"lan": True}, "max_bytes": 3 * 1024 * 1024}, {"path": "/oversize"}).json()
    # /oversize is not JSON: the sample is scrubbed text, truncated
    assert big["truncated"] is True and len(big["sample"].encode()) <= 16 * 1024


# ------------------------------------------------------------------- scrubbing

def test_redact_sample_hides_secret_keys_values_and_token_shapes():
    doc = {"name": "ok", "password": "hunter2", "nested": {"api_key": "k", "Authorization": "Bearer abcdefghij", "fine": 3},
           "token": "x", "note": "use Bearer abcdefghijkl here", "id": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b", "list": [{"secret": 1, "ok": 2}],
           "echo": "contains super-secret-value inside"}
    out = redact_sample(doc, ["super-secret-value"])
    assert out["name"] == "ok" and out["nested"]["fine"] == 3 and out["list"] == [{"secret": "[redacted]", "ok": 2}]
    blob = json.dumps(out)
    for leak in ("hunter2", "abcdefghij", "super-secret-value", "9f86d081"):
        assert leak not in blob
    assert out["password"] == out["token"] == out["nested"]["api_key"] == "[redacted]"


def test_redact_sample_is_bounded():
    deep = cur = {}
    for _ in range(40):
        cur["a"] = {}
        cur = cur["a"]
    assert "too deep" in json.dumps(redact_sample(deep))
    assert len(redact_sample({str(i): i for i in range(1000)})) == 201
    assert len(redact_sample(list(range(1000)))) == 101


def test_scrub_text_removes_values_and_credentials_but_keeps_layout():
    t = "line1\n  Authorization: Bearer abcdefghijk\nkey=super-secret-value\n"
    out = scrub_text(t, ["super-secret-value"])
    assert "abcdefghijk" not in out and "super-secret-value" not in out and out.count("\n") == 3


# ----------------------------------------------------------------- suggestions

def test_suggestions_are_real_paths_with_samples_and_never_secrets():
    doc = {"state": "ok", "uptime": 3725, "cpu_load": 0.25, "disk": {"used_bytes": 512, "total_bytes": 1024},
           "items": [{"name": "alpha", "size": 10}, {"name": "beta", "size": 20}], "updated": "2026-10-01T10:00:00Z",
           "api_key": "abc", "auth": {"x": 1}, "weird key": 1, "tok": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b", "nothing": None,
           "flag": True, "tags": ["a", "b"]}
    out = suggest_fields(doc)
    by = {s["path"]: s for s in out}
    assert by["$.cpu_load"]["format"] == "percent" and by["$.disk.used_bytes"]["format"] == "bytes" and by["$.uptime"]["format"] == "duration"
    assert by["$.items[*].name"]["sample"] == "alpha" and by["$.updated"]["format"] == "relative_time" and by["$.tags[*]"]["sample"] == "a"
    assert by["$.flag"]["format"] == "text"
    for forbidden in ("api_key", "auth", "weird key", "tok", "nothing"):
        assert not any(forbidden in p for p in by)
    for s in out:
        parse_path(s["path"])                                                           # valid for the real mapping engine
        assert extract(doc, s["path"])                                                  # and it finds something
        assert set(s) == {"path", "label", "format", "sample"}


def test_suggestions_are_capped_and_depth_limited():
    doc = {f"k{i}": i for i in range(200)}
    assert len(suggest_fields(doc)) == MAX_SUGGESTIONS
    deep = cur = {}
    for _ in range(12):
        cur["a"] = {}
        cur = cur["a"]
    cur["leaf"] = 1
    assert suggest_fields(deep) == []
    assert suggest_fields([{"x": 1}])[0]["path"] == "$[*].x" and suggest_fields(5) == [] and suggest_fields("s") == []


# --------------------------------------------------------------- rate limit / audit

def test_tries_are_rate_limited_per_minute(env):
    app, c, h, ref = env
    for _ in range(10):
        assert try_(c, h, "svc", {"path": "/status"}).status_code == 200
    r = try_(c, h, "svc", {"path": "/status"})
    assert r.status_code == 429 and 1 <= int(r.headers["retry-after"]) <= 60
    assert len([x for x in ref.calls if x[1] == "/status"]) == 10                      # the 11th never reached the network


def test_rejected_requests_do_not_use_up_the_budget(env):
    app, c, h, ref = env
    for _ in range(30):
        assert try_(c, h, "svc", {"path": "/x", "method": "POST"}).status_code == 422
    assert try_(c, h, "svc", {"path": "/status"}).status_code == 200


def test_every_executed_try_is_in_history_without_bodies(env):
    app, c, h, ref = env
    try_(c, h, "svc", {"path": "/status", "query": {"secretq": "value"}})
    try_(c, h, unsaved(ref, auth={"type": "bearer", "secret_ref": "env:CONNECT_REF_TOKEN"}), {"path": "/secret-echo"})
    try_(c, h, "svc", {"path": "/boom"})
    events = [e for e in c.get("/api/memory/history").json() if e["event"] == "connect_try"]
    assert len(events) == 3
    saved = [e for e in events if e["detail"]["saved"]]
    assert {e["detail"]["path"] for e in saved} == {"/status", "/boom"} and events[0]["actor"] == "owner"
    blob = json.dumps(events)
    for leak in (TOKEN, "Bearer", "secretq", "value", "uptime", "state"):
        assert leak not in blob
    assert [e["detail"]["status_code"] for e in events] == [500, 200, 200] and events[0]["detail"]["error_class"] == "http_5xx"


def test_history_accepts_only_allow_listed_external_events(env):
    from personal_world.worlds.memory_store import MemoryError_
    app, c, h, ref = env
    with pytest.raises(MemoryError_):
        app.state.memory.record_event("created", {"x": 1}, actor="owner")


# ---------------------------------------------------------------------- preview

CARD = {"title": "Server", "fields": [{"path": "$.uptime", "label": "Uptime", "format": "duration"},
                                      {"path": "$.cpu", "label": "CPU", "format": "percent"},
                                      {"path": "$.nope", "label": "Missing", "format": "number"}],
        "status": {"path": "$.state", "healthy": ["ok"]}, "meter": {"type": "progress", "value": "cpu", "max": 1}}
SAMPLE = {"state": "ok", "uptime": 3725, "cpu": 0.256}


def test_preview_from_a_sample_makes_no_network_call_and_matches_the_real_envelope(env):
    app, c, h, ref = env
    r = c.post("/api/connect/preview", json={"card": CARD, "sample": SAMPLE}, headers=h)
    assert r.status_code == 200
    e = r.json()
    assert set(e) == {"card_id", "source_state", "freshness", "observed_at", "fetched_at", "last_good_at", "values", "meter", "meaning", "evidence"}
    assert e["source_state"] == "healthy" and e["freshness"] == "current"
    assert e["values"]["uptime"] == {"text": "1h 2m", "raw": 3725} and e["values"]["cpu"]["text"] == "25.6%"
    assert e["values"]["missing"] == {"text": "unknown"}                                # missing is unknown, never 0
    assert e["meter"]["value"] == 0.256 and e["meter"]["max"] == 1
    assert ref.calls == []
    # the same card saved and built for real gives the same values
    s = app.state.store
    s.save("request", Request(id="svc.pv", provider="svc", path="/status", ttl_s=0))
    from personal_world.worlds.models import Card
    s.save("card", Card.model_validate({"schema_version": 1, "id": "pv", "request": "svc.pv", "meaning": {"concept": "c", "short": "s"}, **CARD}))
    real = app.state.cards.build("pv")
    assert real["values"] == e["values"] and real["meter"]["value"] == e["meter"]["value"] and real["source_state"] == e["source_state"]


def test_preview_status_map_and_defaults(env):
    app, c, h, ref = env
    e = c.post("/api/connect/preview", json={"card": CARD, "sample": {**SAMPLE, "state": "weird"}}, headers=h).json()
    assert e["source_state"] == "unknown"
    bare = c.post("/api/connect/preview", json={"card": {"fields": [{"path": "$.uptime", "label": "Up"}]}, "sample": SAMPLE}, headers=h)
    assert bare.status_code == 200 and bare.json()["values"]["up"]["text"] == "3,725"


def test_preview_from_a_saved_request_reads_once_through_the_runner(env):
    app, c, h, ref = env
    r = c.post("/api/connect/preview", json={"card": CARD, "request": "svc.status"}, headers=h)
    assert r.status_code == 200 and r.json()["values"]["uptime"]["text"] == "1h 2m"
    assert len([x for x in ref.calls if x[1] == "/status"]) == 1
    assert c.post("/api/connect/preview", json={"card": CARD, "request": "svc.go"}, headers=h).status_code == 422     # a write request
    assert c.post("/api/connect/preview", json={"card": CARD, "request": "svc.nope"}, headers=h).status_code == 404
    assert ref.counters.get("ping", 0) == 0


@pytest.mark.parametrize("body,code", [
    ({"card": CARD}, 422), ({"card": CARD, "sample": {}, "request": "svc.status"}, 422), ({"sample": {}}, 422),
    ({"card": 5, "sample": {}}, 422), ({"card": {"fields": [{"path": "$..x", "label": "L"}]}, "sample": {}}, 422),
    ({"card": {"meter": {"type": "progress"}}, "sample": {}}, 422), ({"card": CARD, "sample": {}, "x": 1}, 422)])
def test_preview_validation_is_a_plain_422(env, body, code):
    app, c, h, ref = env
    r = c.post("/api/connect/preview", json=body, headers=h)
    assert r.status_code == code and "Traceback" not in r.text


def test_preview_refuses_oversized_or_absurdly_deep_samples(env):
    app, c, h, ref = env
    assert c.post("/api/connect/preview", json={"card": CARD, "sample": {"x": "y" * 300_000}}, headers=h).status_code == 413
    deep = cur = {}
    for _ in range(40):
        cur["a"] = {}
        cur = cur["a"]
    assert c.post("/api/connect/preview", json={"card": CARD, "sample": deep}, headers=h).status_code == 413


def test_nothing_is_saved_by_try_or_preview(env):
    app, c, h, ref = env
    before = sorted(str(p) for p in app.state.store._worlds.rglob("*.yaml"))
    try_(c, h, unsaved(ref), {"path": "/items"})
    c.post("/api/connect/preview", json={"card": CARD, "sample": SAMPLE}, headers=h)
    assert sorted(str(p) for p in app.state.store._worlds.rglob("*.yaml")) == before
