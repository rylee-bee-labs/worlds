"""Push, the notify door and the PWA shell through the REAL production app: real sessions, CSRF, agent tokens.

The route tests use stand-in principals; these prove the wiring in ``production.create_app``: an owner session
subscribes with its CSRF token, an agent token publishes only with the ``notify`` scope, a dedupe key holds across
calls, and the SPA fallback never shadows the API or health routes.
"""
import pytest
import yaml
from fastapi.testclient import TestClient

from personal_world.worlds.authn import SESSION_COOKIE
from personal_world.worlds.production import create_app

ORIGIN = "https://worlds.example.test"
BOOT = "open-sesame-correct-horse-2"  # pw-safety: synthetic
SUB = {"endpoint": "https://push.example.invalid/device-1",
       "keys": {"p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",  # gitleaks:allow (RFC 8291 test vector)
                "auth": "tBHItJI5svbpez7KI4CCXg"}}  # gitleaks:allow (RFC 8291 test vector)
NOTE = {"tier": "good_news", "source": "projecthome", "title": "A decision needs you", "body": "Which doorway?",
        "link": "/", "dedupe_key": "ph:decision:42"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    monkeypatch.delenv("PW_VAPID_PRIVATE_KEY", raising=False)
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<main>front door</main>")
    (static / "sw.js").write_text("self.addEventListener('push', () => {});")
    monkeypatch.setenv("PW_STATIC_DIR", str(static))
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    (cfg / "owner.yaml").write_text(yaml.safe_dump({
        "schema_version": 1, "public_origin": ORIGIN,
        "bootstrap": {"enabled": True, "secret_ref": "env:PW_TEST_BOOTSTRAP"}}))
    app = create_app(cfg, data)
    return app, TestClient(app, base_url=ORIGIN, follow_redirects=False)


def _owner(app, c):
    assert c.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN}).status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": app.state.auth.csrf_token(c.cookies.get(SESSION_COOKIE))}


def _agent(app, scopes):
    _, token = app.state.auth.tokens.create("project-home", scopes)
    return {"Authorization": f"Bearer {token}"}


def test_an_owner_session_subscribes_with_csrf_and_the_list_hides_credentials(world):
    app, c = world
    h = _owner(app, c)
    assert c.post("/api/push/subscriptions", json={"subscription": SUB}, headers={"Origin": ORIGIN}).status_code == 403
    r = c.post("/api/push/subscriptions", json={"subscription": SUB, "device_label": "Phone"}, headers=h)
    assert r.status_code == 200, r.text
    listing = c.get("/api/push/subscriptions", headers=h)
    assert listing.status_code == 200 and "push.example.invalid" not in listing.text and "p256dh" not in listing.text


def test_an_agent_token_publishes_only_with_notify_and_dedupe_holds(world):
    app, c = world
    c.cookies.clear()
    allowed, other = _agent(app, ["notify"]), _agent(app, ["memory.read"])
    first = c.post("/api/notify", json=NOTE, headers=allowed)
    assert first.status_code == 200, first.text
    again = c.post("/api/notify", json=NOTE, headers=allowed)
    assert again.json()["data"]["state"] == "duplicate" and again.json()["data"]["id"] == first.json()["data"]["id"]
    assert c.post("/api/notify", json=NOTE, headers=other).status_code == 403
    assert c.post("/api/notify", json=NOTE).status_code == 401
    # An agent token can publish, but never read the owner's devices or history.
    assert c.get("/api/push/subscriptions", headers=allowed).status_code == 403
    assert c.get("/api/notifications", headers=allowed).status_code == 403


def test_the_owner_sees_the_published_notification_in_history(world):
    app, c = world
    allowed = _agent(app, ["notify"])
    c.cookies.clear()
    assert c.post("/api/notify", json=NOTE, headers=allowed).status_code == 200
    h = _owner(app, c)
    items = c.get("/api/notifications", headers=h).json()["data"]
    rows = items.get("items", items) if isinstance(items, dict) else items
    assert [n["title"] for n in rows] == ["A decision needs you"]


def test_the_pwa_shell_is_served_and_never_shadows_the_api(world):
    _, c = world
    assert c.get("/").text == "<main>front door</main>"
    assert c.get("/settings").text == "<main>front door</main>"
    sw = c.get("/sw.js")
    assert sw.status_code == 200 and sw.headers["service-worker-allowed"] == "/"
    assert c.get("/healthz").json()["ok"] is True
    assert c.get("/api/auth/session").json()["authenticated"] is False
    assert c.get("/api/no-such-route").status_code == 404
