"""Acceptance tests for personal_world.worlds.server (read API C6 + config CRUD) and seed."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from personal_world.worlds.reference_provider import ReferenceServer, reference_send
from personal_world.worlds.seed import seed_reference_config
from personal_world.worlds.server import build_app

ENVELOPE_KEYS = {"card_id", "source_state", "freshness", "observed_at", "fetched_at", "last_good_at",
                 "values", "meter", "meaning", "evidence"}


@pytest.fixture
def ref():
    with ReferenceServer(token="tok") as s:
        yield s


def make_client(tmp_path, ref, authed=True):
    def principal():
        if not authed:
            raise HTTPException(status_code=401, detail="unauthorized")
        return "owner"

    app = build_app(tmp_path / "cfg", principal_dependency=principal, send_override=reference_send({"REF_TOKEN": "tok"}),
                    data_dir=tmp_path / "data")
    seed_reference_config(app.state.store, ref.base_url)
    return TestClient(app)


def test_every_route_requires_a_principal(tmp_path, ref):
    c = make_client(tmp_path, ref, authed=False)
    for method, url in [("get", "/api/boards/home"), ("get", "/api/cards/reference-status"), ("get", "/api/needs-you"),
                        ("get", "/api/config/provider"), ("put", "/api/config/provider/x"), ("delete", "/api/config/provider/x")]:
        assert getattr(c, method)(url).status_code == 401, url


def test_home_board_defs_route(tmp_path, ref):
    c = make_client(tmp_path, ref)
    r = c.get("/api/boards/home")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "home" and len(body["items"]) >= 4
    for it in body["items"]:
        assert set(it) == {"card", "size", "hidden", "title", "icon", "group", "view", "fields", "meter_type"}
    assert "base_url" not in r.text and "$." not in r.text


def test_card_envelopes_from_reference_provider_cover_scenarios(tmp_path, ref):
    c = make_client(tmp_path, ref)
    states = {}
    for it in c.get("/api/boards/home").json()["items"]:
        e = c.get(f"/api/cards/{it['card']}").json()
        assert set(e) == ENVELOPE_KEYS
        states[it["card"]] = e["source_state"]
    assert states["reference-status"] == "healthy"
    assert states["reference-empty"] == "healthy"
    assert states["reference-down"] == "unavailable"
    assert states["reference-bad-data"] == "degraded"
    assert states["reference-locked"] == "needs_attention"


def test_unknown_card_404_and_needs_you_empty(tmp_path, ref):
    c = make_client(tmp_path, ref)
    assert c.get("/api/cards/nope").status_code == 404
    assert c.get("/api/needs-you").json() == []
    assert c.get("/api/pickup").status_code == 404


def test_config_crud_etag_flow(tmp_path, ref):
    c = make_client(tmp_path, ref)
    lst = c.get("/api/config/provider").json()
    assert any(p["id"] == "reference" for p in lst["items"]) and "errors" in lst
    r = c.get("/api/config/provider/reference")
    assert r.status_code == 200 and r.headers["etag"]
    obj, etag = r.json(), r.headers["etag"]
    obj["name"] = "Renamed"
    assert c.put("/api/config/provider/reference", json=obj, headers={"If-Match": etag}).status_code == 200
    stale = c.put("/api/config/provider/reference", json=obj, headers={"If-Match": etag})
    assert stale.status_code == 409
    assert c.put("/api/config/provider/reference", json=obj).status_code == 428  # If-Match required


def test_config_create_delete_and_validation_errors(tmp_path, ref):
    c = make_client(tmp_path, ref)
    new = {"schema_version": 1, "id": "other", "name": "Other", "kind": "http", "base_url": "http://127.0.0.1:1"}
    assert c.put("/api/config/provider/other", json=new, headers={"If-None-Match": "*"}).status_code == 200
    assert c.put("/api/config/provider/other", json=new, headers={"If-None-Match": "*"}).status_code == 409
    bad = dict(new, base_url="not a url")
    r = c.put("/api/config/provider/other", json=bad, headers={"If-Match": c.get("/api/config/provider/other").headers["etag"]})
    assert r.status_code == 422 and "Traceback" not in r.text
    assert c.put("/api/config/provider/mismatch", json=new, headers={"If-None-Match": "*"}).status_code == 422  # id != url
    assert c.delete("/api/config/provider/reference").status_code == 409  # still referenced
    assert c.delete("/api/config/provider/other").status_code == 204
    assert c.get("/api/config/provider/other").status_code == 404
    assert c.get("/api/config/bogus").status_code == 404


def test_saving_config_never_sends_anything(tmp_path, ref):
    c = make_client(tmp_path, ref)
    before = len(ref.calls)
    req = c.get("/api/config/request/reference.status").json()
    c.put("/api/config/request/reference.status", json=req,
          headers={"If-Match": c.get("/api/config/request/reference.status").headers["etag"]})
    assert len(ref.calls) == before


def test_write_request_cannot_be_run_by_a_card(tmp_path, ref):
    c = make_client(tmp_path, ref)
    c.put("/api/config/request/reference.ping", json={"schema_version": 1, "id": "reference.ping", "provider": "reference",
                                                      "method": "POST", "path": "/actions/ping"}, headers={"If-None-Match": "*"})
    card = {"schema_version": 1, "id": "pinger", "title": "P", "request": "reference.ping",
            "meaning": {"concept": "x", "short": "s"}}
    assert c.put("/api/config/card/pinger", json=card, headers={"If-None-Match": "*"}).status_code == 200
    e = c.get("/api/cards/pinger").json()
    assert e["source_state"] == "unavailable" and ref.counters.get("ping", 0) == 0


def test_secret_values_never_in_any_response(tmp_path, ref):
    c = make_client(tmp_path, ref)
    blob = c.get("/api/config/provider").text + c.get("/api/cards/reference-locked").text
    assert "tok" not in blob.replace("token", "").replace("Token", "")
    assert "REF_TOKEN" in blob  # names only


def test_app_lifespan_healthz(tmp_path, ref):
    c = make_client(tmp_path, ref)
    assert c.get("/healthz").status_code == 200  # healthz is public and has no auth dependency


def test_if_match_star_is_refused(tmp_path, ref):
    c = make_client(tmp_path, ref)
    obj = c.get("/api/config/provider/reference").json()
    assert c.put("/api/config/provider/reference", json=obj, headers={"If-Match": "*"}).status_code == 428


def test_home_is_a_guided_first_run_when_there_is_nothing_to_show(tmp_path):
    app = build_app(tmp_path / "cfg", principal_dependency=lambda: "owner", send_override=lambda *a, **k: None)
    c = TestClient(app, base_url="http://127.0.0.1")
    r = c.get("/api/boards/home")
    assert r.status_code == 200                                    # never a 404: first run is a state, not an error
    assert r.json() == {"id": "home", "title": "Home", "items": [], "first_run": True}


def test_first_run_ends_once_there_is_a_card(tmp_path, ref):
    c = make_client(tmp_path, ref)
    body = c.get("/api/boards/home").json()
    assert body["first_run"] is False and body["items"]


def test_an_empty_configured_home_board_is_still_first_run(tmp_path):
    app = build_app(tmp_path / "cfg", principal_dependency=lambda: "owner", send_override=lambda *a, **k: None)
    c = TestClient(app, base_url="http://127.0.0.1")
    c.put("/api/config/board/home", json={"schema_version": 1, "id": "home", "title": "Mine", "home": True, "items": []},
          headers={"If-None-Match": "*"})
    body = c.get("/api/boards/home").json()
    assert body["title"] == "Mine" and body["items"] == [] and body["first_run"] is True
