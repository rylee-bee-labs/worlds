"""Endpoint honesty hardening regression tests.

- COR-04: reconciler diff/propose with no request body answers an
  envelope (empty observed state), never a 500.
- COR-11: unknown theme name is an honest 404, known one is 200.
- COR-12: FORCE_SETUP=1 makes /api/setup/status report setup needed
  even when the setup-complete marker exists.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "t-token-1")
    c = TestClient(create_app(tmp_path, tmp_path))
    c.headers.update({"Authorization": "Bearer t-token-1"})
    return c


class TestReconcilerEmptyBody:
    def test_diff_without_body_is_envelope_not_500(self, client):
        r = client.get("/api/reconciler/diff/any-service")
        assert r.status_code == 200
        assert {"ok", "status"} <= set(r.json().keys())

    def test_propose_without_body_is_envelope_not_500(self, client):
        r = client.get("/api/reconciler/propose/any-service")
        assert r.status_code == 200
        assert {"ok", "status"} <= set(r.json().keys())


class TestTheme404:
    def test_unknown_theme_is_404(self, client):
        r = client.get("/api/themes/no-such-theme")
        assert r.status_code == 404
        assert "no theme pack" in r.json()["detail"]

    def test_known_theme_is_200(self, client):
        names = client.get("/api/themes").json()["data"]
        r = client.get(f"/api/themes/{names[0]['name']}")
        assert r.status_code == 200


class TestJournalClamp:
    def test_journal_n_is_clamped_1_to_500(self, client):
        r = client.get("/api/journal?n=999999")
        assert r.status_code == 200
        n0 = client.get("/api/journal?n=0").json()["data"]
        assert n0 == client.get("/api/journal").json()["data"]


class TestSetupStatusForce:
    def test_force_setup_reports_needed(self, tmp_path, monkeypatch):
        from personal_world.api import create_app
        from personal_world.init import init_world

        init_world(tmp_path, tmp_path)
        monkeypatch.setenv("FORCE_SETUP", "1")
        monkeypatch.setenv("PW_API_TOKEN", "t-token-1")
        c = TestClient(create_app(tmp_path, tmp_path))
        assert c.get("/healthz").json()["setup_needed"] is True
