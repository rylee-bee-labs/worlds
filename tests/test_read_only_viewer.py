"""A read-only viewer credential acts as the owning person for reads only.

Enforced in the auth layer (``require_auth`` / ``require_step_up``), not
per route: only GET/HEAD/OPTIONS succeed, step-up is never granted (not by
session, loopback or delegated header), and an explicit deny list keeps
secret values and raw personal material closed.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "instancetoken"  # pw-safety: synthetic
OWNER = {"Authorization": f"Bearer {TOKEN}"}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(params=["single", "multi"])
def env(request, tmp_path, monkeypatch):
    import personal_world.api as api_mod
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("PW_PROXY_STEPUP_SECRET", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PW_IDENTITY_MODE", request.param)
    app = create_app(tmp_path, tmp_path)
    client = TestClient(app)

    def make_viewer(viewer_id="uat-view"):
        r = client.post(
            "/api/identity/viewers", json={"viewer_id": viewer_id, "label": "walk"}, headers=OWNER
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]["token"]

    return client, app, make_viewer, tmp_path, monkeypatch, api_mod


PERSON_ONLY_READS = [
    "/api/prefs",
    "/api/notifications/prefs",
    "/api/sections",
    "/api/briefing",
    "/api/place",
    "/api/lore",
    "/api/later",
    "/api/me",
    "/api/status",
    "/api/crew",
]


def test_viewer_reads_person_only_routes_that_an_agent_cannot(env):
    client, _app, make_viewer, *_ = env
    viewer = _h(make_viewer())
    agent = client.post(
        "/api/identity/agents", json={"agent_id": "walker", "scopes": ["read"]}, headers=OWNER
    ).json()["data"]["token"]
    for path in PERSON_ONLY_READS:
        r = client.get(path, headers=viewer)
        assert r.status_code == 200, (path, r.status_code, r.text[:120])
    assert client.get("/api/prefs", headers=_h(agent)).status_code == 403


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_every_write_method_is_refused(env, method):
    client, _app, make_viewer, *_ = env
    viewer = _h(make_viewer())
    for path in ("/api/prefs", "/api/lore/confirm", "/api/remember", "/api/daily", "/api/identity/agents", "/api/does-not-exist"):
        r = client.request(method, path, json={}, headers=viewer)
        assert r.status_code in (403, 404, 405), (method, path, r.status_code)
        if path != "/api/does-not-exist" and r.status_code == 403:
            assert "read-only token" in r.text, (method, path, r.text)
    # a route that exists for the method must say why
    r = client.put("/api/prefs", json={"text_scale": 1.5}, headers=viewer)
    assert r.status_code == 403 and "read-only token" in r.text
    r = client.post("/api/daily", headers=viewer)
    assert r.status_code == 403 and "read-only token" in r.text


def test_step_up_is_never_granted(env):
    client, _app, make_viewer, tmp_path, monkeypatch, api_mod = env
    viewer = _h(make_viewer())
    # loopback peer (the test client's), the delegated header, and both together
    monkeypatch.setenv("PW_PROXY_STEPUP_SECRET", "proxy-secret-synthetic")  # pw-safety: synthetic
    delegated = {
        **viewer,
        "X-PW-StepUp": "1",
        "X-PW-Proxy-StepUp-Secret": "proxy-secret-synthetic",  # pw-safety: synthetic
    }
    for headers in (viewer, delegated):
        r = client.post("/api/identity/agents", json={"agent_id": "x-agent"}, headers=headers)
        assert r.status_code == 403 and "read-only token" in r.text, r.text
    # the token cannot be traded for a session or an elevation either
    for path, body in (("/api/auth/login", {"token": viewer["Authorization"][7:]}), ("/api/auth/step-up", {"token": viewer["Authorization"][7:]})):
        r = client.post(path, json=body)
        assert r.status_code in (400, 401, 403), (path, r.status_code)
    assert "pw_session" not in client.cookies
    # and the owner is unaffected
    assert client.post("/api/identity/agents", json={"agent_id": "ok-agent"}, headers=OWNER).status_code == 200


def test_denied_sensitive_reads_are_403(env):
    client, _app, make_viewer, *_ = env
    from personal_world.api import VIEWER_DENIED_PREFIXES

    viewer = _h(make_viewer())
    from personal_world.api import _viewer_refusal
    from personal_world.identity import Principal

    ro = Principal(id="primary", read_only=True)
    for prefix in VIEWER_DENIED_PREFIXES:
        assert _viewer_refusal(ro, "GET", prefix), prefix
        assert _viewer_refusal(ro, "GET", prefix + "/anything"), prefix
        assert not _viewer_refusal(ro, "GET", prefix + "x-not-a-child"), prefix
    assert not _viewer_refusal(Principal(id="primary"), "GET", "/api/vault/x")
    for path in ("/api/vault/wifi", "/api/journal?n=5", "/api/recall?q=x", "/api/backup", "/api/exports/world", "/api/worlds/backup/download/abc", "/api/identity/users"):
        assert client.get(path, headers=viewer).status_code == 403, path


def test_deny_list_names_the_sensitive_routes():
    from personal_world.api import VIEWER_DENIED_PREFIXES as D

    for must in ("/api/vault", "/api/secrets", "/api/recall", "/api/journal", "/api/backup", "/api/worlds", "/api/exports", "/api/identity/agents", "/api/identity/viewers"):
        assert must in D


def test_creation_listing_and_revocation(env):
    client, _app, make_viewer, tmp_path, *_ = env
    token = make_viewer()
    assert token.startswith("pwv_")
    # stored hashed, never in clear
    assert token not in (tmp_path / "users.json").read_text()
    listed = client.get("/api/identity/viewers", headers=OWNER).json()["data"]
    assert [v["viewer_id"] for v in listed] == ["uat-view"]
    assert "hashed_tokens" not in listed[0] and token not in str(listed)
    # revoke (owner + step-up) -> 401
    assert client.get("/api/prefs", headers=_h(token)).status_code == 200
    assert client.delete("/api/identity/viewers/uat-view", headers=OWNER).status_code == 200
    assert client.get("/api/prefs", headers=_h(token)).status_code == 401
    assert client.get("/api/identity/viewers", headers=OWNER).json()["data"] == []
    assert client.delete("/api/identity/viewers/uat-view", headers=OWNER).status_code == 404


def test_only_the_owner_can_create_list_or_revoke(env):
    client, _app, make_viewer, *_ = env
    token = make_viewer()
    agent = client.post(
        "/api/identity/agents", json={"agent_id": "walker", "scopes": ["read"]}, headers=OWNER
    ).json()["data"]["token"]
    for who in (_h(token), _h(agent)):
        assert client.get("/api/identity/viewers", headers=who).status_code == 403
        assert client.post("/api/identity/viewers", json={"viewer_id": "more"}, headers=who).status_code == 403
        assert client.delete("/api/identity/viewers/uat-view", headers=who).status_code == 403
    assert client.post("/api/identity/viewers", json={"viewer_id": ""}, headers=OWNER).status_code == 422
    assert client.post("/api/identity/viewers", json={"viewer_id": "uat-view"}, headers=OWNER).status_code == 409


def test_member_cannot_create_a_viewer(tmp_path, monkeypatch):
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    c = TestClient(create_app(tmp_path, tmp_path))
    r = c.post("/api/identity/users", json={"user_id": "beta", "display_name": "Made up person"}, headers=OWNER)
    member = _h(r.json()["data"]["token"])
    assert c.post("/api/identity/viewers", json={"viewer_id": "v"}, headers=member).status_code == 403


def test_a_disabled_owner_takes_the_viewer_with_it(tmp_path, monkeypatch):
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    from personal_world.identity import IdentityStore

    c = TestClient(create_app(tmp_path, tmp_path))
    store = IdentityStore(tmp_path)
    store.create_user("ghost", "Made up person")
    store.create_viewer("gv", "ghost", "pwv_synthetic-token", label="x")  # pw-safety: synthetic
    assert c.get("/api/me", headers=_h("pwv_synthetic-token")).status_code == 200  # pw-safety: synthetic
    store.disable_user("ghost")
    assert c.get("/api/me", headers=_h("pwv_synthetic-token")).status_code == 401  # pw-safety: synthetic


def test_existing_agent_and_person_auth_are_unchanged(env):
    client, _app, make_viewer, *_ = env
    make_viewer()
    agent = client.post(
        "/api/identity/agents", json={"agent_id": "walker", "scopes": ["read"]}, headers=OWNER
    ).json()["data"]["token"]
    assert client.get("/api/status", headers=_h(agent)).status_code == 200
    assert client.get("/api/prefs", headers=_h(agent)).status_code == 403  # person-only
    assert client.get("/api/vault/status", headers=OWNER).status_code == 200
    assert client.put("/api/prefs", json={"text_scale": 1.25}, headers=OWNER).status_code == 200
    assert client.get("/api/status", headers=_h("wrong")).status_code == 401


# The routes below authenticate by themselves (first-run, sign-in, session
# and invite flows) rather than through require_auth; a bearer viewer token
# holds no session and cannot use them. Adding a new non-GET route without
# require_auth / require_step_up and without listing it here fails the test
# below, on purpose.
SELF_AUTHENTICATING = {
    "/api/auth/login",
    "/api/auth/oidc/link",
    "/api/auth/logout",
    "/api/auth/step-up",
    "/api/setup-wizard/provision",
    "/api/setup-wizard/test-oidc",
    "/api/setup-wizard/auth-choice",
    "/api/setup-wizard/comfort",
    "/api/setup-wizard/companion",
    "/api/setup-wizard/finish",
    "/api/setup",
    "/api/invites/accept",
}


def test_every_non_get_route_refuses_a_viewer_or_is_declared_self_authenticating(env):
    client, app, make_viewer, *_ = env
    viewer = _h(make_viewer())
    checked = 0
    # First-run routes answer by instance state, not by credential, and
    # change that state: exercise them last and only check they are declared.
    ordered = sorted(app.routes, key=lambda r: getattr(r, "path", "").startswith("/api/setup"))
    for route in ordered:
        methods = (getattr(route, "methods", None) or set()) - {"GET", "HEAD", "OPTIONS"}
        if not methods or not route.path.startswith("/api"):
            continue
        names = {getattr(d.call, "__name__", "") for d in route.dependant.dependencies}
        path = route.path.replace("{", "").replace("}", "") if "{" in route.path else route.path
        for method in methods:
            r = client.request(method, path, json={}, headers=viewer)
            if names & {"require_auth", "require_step_up"}:
                assert r.status_code == 403 and "read-only token" in r.text, (method, route.path, r.status_code, r.text[:100])
                checked += 1
            else:
                assert route.path in SELF_AUTHENTICATING, f"{method} {route.path} has no auth dependency and is not declared"
                first_run = route.path.startswith("/api/setup")
                if route.path != "/api/auth/logout" and not first_run:  # logout: no session to end
                    assert r.status_code != 200, (method, route.path)
    assert checked > 60


# ── Memory and Chat: structure yes, content no ──────────────────────────


def _seed_chat(tmp_path, mode):
    from personal_world.chat_history import ChatHistory
    from personal_world.identity import Principal, principal_scoped_path

    path = principal_scoped_path(tmp_path, Principal(id="primary"), "chat_history", mode=mode)
    h = ChatHistory(path)
    h.append("user", "SECRET-SAID-BY-PERSON")  # pw-safety: synthetic
    h.append("assistant", "SECRET-SAID-BY-COMPANION")  # pw-safety: synthetic


def test_chat_history_gives_a_viewer_structure_but_never_what_was_said(env):
    client, app, make_viewer, tmp_path, *_ = env
    mode = "multi" if "multi" in str(app.state.identity["mode"]) else "single"
    _seed_chat(tmp_path, mode)
    viewer = _h(make_viewer())
    r = client.get("/api/chat/history", headers=viewer)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["count"] == 2
    assert [set(e) for e in data["entries"]] == [{"ts", "role"}, {"ts", "role"}]
    assert "SECRET-SAID" not in r.text
    # the owner still gets the full transcript
    assert "SECRET-SAID-BY-PERSON" in client.get("/api/chat/history", headers=OWNER).text


def test_records_categories_are_structure_and_records_are_content(env):
    client, _app, make_viewer, *_ = env
    viewer = _h(make_viewer())
    r = client.get("/api/records/categories", headers=viewer)
    assert r.status_code == 200, r.text
    assert "categories" in r.text
    for path in ("/api/records", "/api/records?category=medical"):
        assert client.get(path, headers=viewer).status_code == 403, path
    from personal_world.api import _viewer_refusal
    from personal_world.identity import Principal

    ro = Principal(id="primary", read_only=True)
    for path in ("/api/records/categories/x", "/api/records/other", "/api/records/categories2"):
        assert _viewer_refusal(ro, "GET", path), path


def test_memory_search_stays_denied_and_the_exceptions_are_only_the_named_ones(env):
    client, *_ = env
    from personal_world.api import VIEWER_ALLOWED_EXACT

    assert VIEWER_ALLOWED_EXACT == ("/api/records/categories",)
    make = env[2]
    viewer = _h(make())
    for path in ("/api/memory/search?q=x", "/api/recall?q=x", "/api/journal", "/api/journal/last", "/api/vault/status", "/api/backup", "/api/exports/story"):
        assert client.get(path, headers=viewer).status_code == 403, path
