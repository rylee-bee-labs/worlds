"""Serving boundary — the rebuild IS the interface (owner decision 2026-09-22).

`/` serves the React interface (app_router, mounted last); `/login` +
`/setup` stay server-rendered; the retired `/station` and `/vnext` paths
only redirect. Guards here: API and static routes keep winning over the
SPA fallback, reserved namespaces never fall back, and no private value
is echoed into any served HTML.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "instancetoken-do-not-leak-7f3a"  # pw-safety: synthetic
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _app(tmp_path, monkeypatch, setup_done=True):
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    # Deterministic regardless of whether a build happens to be staged
    # in the checkout: point the interface at an empty directory. Tests
    # that want a build stage one themselves (see test_station_ui.py).
    monkeypatch.setenv("PW_APP_DIST", str(tmp_path / "no-app-staged"))
    init_world(tmp_path, tmp_path)
    marker = tmp_path / "setup-complete"
    marker.write_text("ok")
    if not setup_done:
        marker.unlink()
    return TestClient(create_app(tmp_path, tmp_path))


class TestEntryPoint:
    def test_root_redirects_to_login_when_unauthenticated(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"

    def test_first_run_root_redirects_to_setup(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch, setup_done=False)
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/setup"

    def test_missing_build_reports_honestly_when_authenticated(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        r = client.get("/", headers=AUTH)
        assert r.status_code == 503
        assert "not built" in r.text.lower()
        assert str(tmp_path) not in r.text

    @pytest.mark.parametrize(
        "path", ["/station", "/station/", "/station/map", "/vnext", "/vnext/deep"]
    )
    def test_retired_paths_only_redirect(self, tmp_path, monkeypatch, path):
        client = _app(tmp_path, monkeypatch)
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 307
        assert r.headers["location"] == "/"


class TestLoginPage:
    def test_login_page_is_server_rendered(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        r = client.get("/login")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "<form" in r.text
        assert 'id="token"' in r.text
        assert "Access code" in r.text
        assert "/api/auth/login" in r.text
        # First-run naming (owner decision 2026-09-22): "Worlds" on
        # the threshold surfaces; "Project Worlds" stays docs-only.
        assert ">Worlds<" in r.text
        assert "Project Worlds" not in r.text

    def test_login_page_is_not_cached(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        assert client.get("/login").headers["Cache-Control"] == "no-store"

    def test_bare_login_redirects(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        r = client.get("/login/", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"

    def test_first_run_login_redirects_to_setup(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch, setup_done=False)
        r = client.get("/login", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/setup"

    def test_login_page_carries_no_secret(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        r = client.get("/login")
        assert TOKEN not in r.text
        assert "Bearer" not in r.text

    def test_no_dead_setup_link_post_setup(self, tmp_path, monkeypatch):
        # Setup is already complete, so /setup redirects away; the login
        # page must not offer a "build your world" link that just loops
        # back through / to the Station and then here again.
        client = _app(tmp_path, monkeypatch)
        assert 'href="/setup"' not in client.get("/login").text

    def test_login_is_passkey_first_with_code_fallback(self, tmp_path, monkeypatch):
        # The page ships both paths; the client reveals the SSO button and
        # folds the access code away when /api/auth/oidc/status says
        # configured (no password to remember for passkey users).
        text = _app(tmp_path, monkeypatch).get("/login").text
        assert 'id="oidc-btn"' in text
        assert 'id="code-block"' in text
        assert "/api/auth/oidc/status" in text
        assert "/api/auth/oidc/login" in text


class TestApiRoutesNeverSwallowed:
    def test_unknown_api_route_is_json_404(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        r = client.get("/api/definitely-not-a-route")
        assert r.status_code == 404
        assert r.headers["content-type"].startswith("application/json")

    def test_bare_api_path_is_404(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        assert client.get("/api").status_code == 404

    def test_api_status_still_works(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        r = client.get("/api/status", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_healthz_still_works(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        assert client.get("/healthz").json()["ok"] is True

    def test_unauthenticated_api_gets_401(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        assert client.get("/api/sections").status_code == 401


class TestStaticRoutesStillWin:
    def test_companion_svg(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        r = client.get("/companions/personal-world.svg")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/svg+xml"

    def test_icon_sprite(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        assert client.get("/icons/sprite.svg").status_code == 200

    def test_today_art_allowlisted(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        for name in ("settle-gesture", "waves-ladder"):
            r = client.get(f"/today/{name}.svg")
            assert r.status_code == 200, name
        assert client.get("/today/not-in-allowlist.svg").status_code == 404


class TestTraversal:
    def test_dotdot_path_cannot_escape(self, tmp_path, monkeypatch):
        client = _app(tmp_path, monkeypatch)
        (tmp_path / "secret.txt").write_text("TOP SECRET")
        for path in ("/../secret.txt", "/%2e%2e/secret.txt"):
            r = client.get(path)
            assert r.status_code in (200, 303, 404), path
            assert "TOP SECRET" not in (r.text or "")
