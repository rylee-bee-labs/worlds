"""The interface served same-origin at `/` (owner decision 2026-09-22).

`station_ui.app_router` serves the React rebuild at `/` — the one and only
interface — mounted last so it never shadows an API route. These tests
guard the boundaries that make that safe:

* first-run wins — before the setup marker, `/` redirects to `/setup`;
* authorization is the canonical seam — an unauthenticated browser is
  redirected to `/login`, and a valid `pw_session` cookie is enough;
* the served set is an allowlist: traversal cannot escape, internal
  notes (`.md`) and dot/underscore directories are never served;
* reserved namespaces (`/api/…`, `/static/…`) answer JSON 404 — the SPA
  fallback never swallows a namespace it does not own;
* unknown non-reserved paths serve index.html (client-side routing);
* the retired `/station/*` and `/vnext/*` paths only redirect to `/`;
* a deployment without the build says so plainly (503) and never echoes
  a filesystem path.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.station_ui import build_allowlist, default_app_dir  # noqa: E402

TOKEN = "instancetoken-do-not-leak-9a2e"  # pw-safety: synthetic
AUTH = {"Authorization": f"Bearer {TOKEN}"}

INDEX = (
    "<!doctype html><html><head><title>Worlds</title></head>"
    '<body><div id="root"></div><script src="/assets/app.js"></script></body></html>'
)


@pytest.fixture
def dist(tmp_path):
    """A small, deterministic interface build stand-in."""
    root = tmp_path / "app-dist"
    (root / "assets").mkdir(parents=True)
    (root / "_excluded").mkdir(parents=True)
    root.joinpath("index.html").write_text(INDEX)
    root.joinpath("assets", "app.css").write_text("body { color: #fff; }")
    root.joinpath("assets", "app.js").write_text("window.PW = {};")
    root.joinpath("manifest.json").write_text('{"name":"Worlds"}')
    root.joinpath("favicon.svg").write_text("<svg/>")
    root.joinpath("icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    # must never be served: internal notes and excluded directories
    root.joinpath("BUILD-NOTES.md").write_text("internal 192.0.2.7 note")
    root.joinpath("_excluded", "secret.html").write_text("not part of the UI")
    # a sibling secret outside the served root
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    return root


def _client(tmp_path, monkeypatch, dist_dir, setup_done=True):
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PW_APP_DIST", str(dist_dir))
    init_world(tmp_path, tmp_path)
    marker = tmp_path / "setup-complete"
    if setup_done:
        marker.write_text("ok")
    else:
        marker.unlink(missing_ok=True)
    return TestClient(create_app(tmp_path, tmp_path))


@pytest.fixture
def client(tmp_path, monkeypatch, dist):
    return _client(tmp_path, monkeypatch, dist)


def _session(client) -> dict:
    """A real browser session, presented the way a browser presents it.

    The cookie is `Secure`, and the test client speaks plain http, so the
    jar will not send it; the header is set explicitly. That is a test
    transport detail, not a product shortcut — over HTTPS (or on
    localhost) the browser sends it itself.
    """
    response = client.post("/api/auth/login", json={"token": TOKEN})
    assert response.status_code == 200
    sid = response.json()["data"]["session_id"]
    return {"Cookie": f"pw_session={sid}"}


class TestGate:
    def test_first_run_redirects_to_setup(self, tmp_path, monkeypatch, dist):
        c = _client(tmp_path, monkeypatch, dist, setup_done=False)
        r = c.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/setup"

    def test_unauthenticated_redirects_to_login(self, client):
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"

    def test_session_cookie_is_enough(self, client):
        r = client.get("/", headers=_session(client))
        assert r.status_code == 200
        assert 'id="root"' in r.text

    def test_bearer_also_works(self, client):
        assert client.get("/", headers=AUTH).status_code == 200

    def test_a_bad_session_is_redirected_not_served(self, client):
        r = client.get("/", headers={"Cookie": "pw_session=nonsense"}, follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/login"


class TestServing:
    def test_index_and_assets(self, client):
        session = _session(client)
        r = client.get("/assets/app.js", headers=session)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/javascript")
        assert "window.PW" in r.text
        css = client.get("/assets/app.css", headers=session)
        assert css.status_code == 200
        assert css.headers["content-type"].startswith("text/css")

    def test_binary_asset_served(self, client):
        r = client.get("/icon.png", headers=_session(client))
        assert r.status_code == 200
        assert r.content == b"\x89PNG\r\n\x1a\n"

    def test_assets_revalidate_never_immutable(self, client):
        r = client.get("/assets/app.css", headers=_session(client))
        assert "no-cache" in r.headers["cache-control"] or "must-revalidate" in r.headers["cache-control"]
        assert "immutable" not in r.headers["cache-control"]

    def test_interface_page_carries_a_report_only_policy(self, client):
        session = _session(client)
        for path in ("/", "/some/deep/link"):
            r = client.get(path, headers=session)
            assert r.status_code == 200
            csp = r.headers["content-security-policy-report-only"]
            assert "default-src 'self'" in csp and "object-src 'none'" in csp
            # report-only: nothing may be enforced yet
            assert "content-security-policy" not in {k.lower() for k in r.headers}
        assets = client.get("/assets/app.js", headers=session)
        assert "content-security-policy-report-only" not in assets.headers

    def test_unknown_path_serves_the_spa(self, client):
        # Client-side routing: an unknown document path is index.html,
        # not a 404 dead end.
        r = client.get("/some/deep/link", headers=_session(client))
        assert r.status_code == 200
        assert 'id="root"' in r.text

    def test_reserved_namespaces_stay_json_404(self, client):
        session = _session(client)
        for path in ("/api/definitely-not-a-route", "/static/nope.css"):
            r = client.get(path, headers=session)
            assert r.status_code == 404, path
            assert r.headers["content-type"].startswith("application/json"), path


class TestRetiredPaths:
    @pytest.mark.parametrize(
        "path",
        ["/station", "/station/", "/station/anything", "/vnext", "/vnext/", "/vnext/deep/path"],
    )
    def test_legacy_paths_redirect_to_the_interface(self, client, path):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 307
        assert r.headers["location"] == "/"


class TestAllowlist:
    def test_internal_notes_are_never_served(self, client):
        r = client.get("/BUILD-NOTES.md", headers=_session(client))
        # not served as a file; falls through to the SPA (index), and the
        # note's content never appears
        assert "internal 192.0.2.7 note" not in r.text

    def test_excluded_directories_are_not_served(self, client):
        r = client.get("/_excluded/secret.html", headers=_session(client))
        assert "not part of the UI" not in r.text

    def test_allowlist_excludes_notes_and_underscore_dirs(self, dist):
        allow = build_allowlist(dist)
        assert "index.html" in allow
        assert "assets/app.js" in allow
        assert "BUILD-NOTES.md" not in allow
        assert not any(k.startswith("_") for k in allow)

    def test_allowlist_of_a_missing_dir_is_empty(self, tmp_path):
        assert build_allowlist(tmp_path / "nope") == {}

    def test_traversal_cannot_escape(self, client, dist):
        session = _session(client)
        for path in (
            "/../secret.txt",
            "/%2e%2e/secret.txt",
            "/assets/../../secret.txt",
            "/..%2fsecret.txt",
        ):
            r = client.get(path, headers=session)
            assert "TOP SECRET" not in (r.text or ""), path


class TestHonestAbsence:
    def test_missing_build_reports_503_without_leaking_a_path(
        self, tmp_path, monkeypatch
    ):
        empty = tmp_path / "no-build-here"
        c = _client(tmp_path, monkeypatch, empty)
        r = c.get("/", headers=AUTH)
        assert r.status_code == 503
        assert "not built" in r.text.lower()
        assert str(empty) not in r.text
        assert str(tmp_path) not in r.text


class TestDefaultLocation:
    def test_default_is_static_app_under_the_package(self):
        p = default_app_dir()
        assert p.name == "app"
        assert p.parent.name == "static"
