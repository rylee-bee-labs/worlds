import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from personal_world.push import PushHub
from personal_world.worlds.authn import Principal
from personal_world.worlds.push_routes import register_push_routes


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.delenv("PW_VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("PW_VAPID_SUBJECT", raising=False)
    hub = PushHub(tmp_path, store_path=lambda person, kind: tmp_path / "push" / person / f"{kind}.json")
    hub.now = lambda: 1791828000.0   # 2026-10-12 18:00Z: midday, outside any quiet hours, so the result never depends on the clock
    app = FastAPI()
    def owner(request: Request):
        if request.headers.get("authorization") == "Bearer agent-no":
            raise HTTPException(403, "owner only")
        if not request.headers.get("authorization"):
            raise HTTPException(401, "unauthorized")
        return Principal("owner", "owner")
    def anyone(request: Request):
        auth = request.headers.get("authorization")
        if not auth:
            raise HTTPException(401, "unauthorized")
        if auth == "Bearer notify":
            return Principal("agent", "agent-id", ("notify",), via="token")
        if auth == "Bearer agent-no":
            return Principal("agent", "agent-id", (), via="token")
        return Principal("owner", "owner")
    register_push_routes(app, hub, owner=owner, anyone=anyone)
    return TestClient(app), hub


def test_subscription_list_hides_credentials_and_delete(setup):
    client, _ = setup
    headers = {"Authorization": "Bearer owner"}
    subscription = {"endpoint": "https://push.example.test/endpoint", "keys": {"p256dh": "pub-key", "auth": "auth-key"}}
    created = client.post("/api/push/subscriptions", headers=headers, json={"subscription": subscription, "device_label": "Phone"})
    assert created.status_code == 200
    sid = created.json()["data"]["id"]
    listing = client.get("/api/push/subscriptions", headers=headers)
    assert listing.status_code == 200 and listing.json()["data"][0]["device_label"] == "Phone"
    assert "endpoint" not in listing.text and "p256dh" not in listing.text and "auth-key" not in listing.text
    assert client.delete(f"/api/push/subscriptions/{sid}", headers=headers).status_code == 200


def test_test_route_reports_no_vapid(setup):
    client, _ = setup
    result = client.post("/api/notifications/test", headers={"Authorization": "Bearer owner"}).json()
    assert result["data"]["state"] == "not_configured"


def test_notify_owner_scoped_agent_auth_and_dedupe(setup):
    client, _ = setup
    body = {"tier": "good_news", "source": "home", "title": "Need", "body": "Something needs you", "dedupe_key": "need-1"}
    owner = {"Authorization": "Bearer owner"}
    assert client.post("/api/notify", headers=owner, json=body).json()["data"]["state"] == "not_configured"
    assert client.post("/api/notify", headers=owner, json=body).json()["data"]["state"] == "duplicate"
    assert client.post("/api/notify", headers={"Authorization": "Bearer notify"}, json={**body, "dedupe_key": "need-2"}).status_code == 200
    assert client.post("/api/notify", headers={"Authorization": "Bearer agent-no"}, json=body).status_code == 403
    assert client.post("/api/notify", json=body).status_code == 401


@pytest.mark.parametrize("change", [
    {"tier": "bad"}, {"source": "bad source"}, {"title": ""}, {"title": "x" * 121},
    {"body": ""}, {"body": "x" * 4001}, {"link": "https://elsewhere.test/"},
    {"dedupe_key": "x" * 121}, {"private": "yes"},
])
def test_notify_validation_returns_422(setup, change):
    client, _ = setup
    body = {"tier": "good_news", "source": "home", "title": "Need", "body": "Message", **change}
    assert client.post("/api/notify", headers={"Authorization": "Bearer owner"}, json=body).status_code == 422


def test_notify_rate_limit_after_thirty(setup):
    client, _ = setup
    headers = {"Authorization": "Bearer owner"}
    body = {"tier": "good_news", "source": "home", "title": "Need", "body": "Message"}
    assert all(client.post("/api/notify", headers=headers, json=body).status_code == 200 for _ in range(30))
    assert client.post("/api/notify", headers=headers, json=body).status_code == 429
