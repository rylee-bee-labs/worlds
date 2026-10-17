"""Scoped step-up relaxation: PUT/PATCH /api/prefs, POST
/api/discovery/interests and PUT /api/identity/principal accept a plain
authenticated (single-factor) request instead of demanding a live
step-up grant. POST /api/lore/confirm is NOT among them: it keeps the
step-up.

Why these three are relaxed: each is the caller changing their own
preferences, display name or interests. The data is their own, the
change is reversible, and nothing here touches another person's data or
a secret, so the most a stolen session could do is a nuisance. Each
route keeps an internal person-only check (agent keys are refused).
Confirming lore is different: it changes what Worlds treats as true
about the person, so it stays behind "Confirm it's you" (fresh sign-in
or credential). Every other require_step_up route is untouched;
POST /api/identity/agents is pinned here as a still-gated control.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "instancetoken"  # pw-safety: synthetic
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    import personal_world.api as api_mod
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("PW_PROXY_STEPUP_SECRET", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    c = TestClient(create_app(tmp_path, tmp_path))
    # TestClient requests present with host "testclient", which
    # _is_true_loopback treats as the documented loopback exception —
    # that would satisfy require_step_up too and hide the very
    # distinction this file exists to pin (the red-path idiom
    # test_records.py / test_lore_sync.py already use). Turn it off so a
    # plain AUTH header with no step-up grant is the only thing on offer.
    monkeypatch.setattr(api_mod, "_is_true_loopback", lambda request: False)
    return c


class TestScopedStepUpRelaxation:
    """The routes moved from require_step_up to require_auth now
    accept a plain single-factor session — no step-up grant needed."""

    def test_put_prefs_accepts_plain_auth(self, client):
        r = client.put("/api/prefs", json={"text_scale": 1.25}, headers=AUTH)
        assert r.status_code == 200, r.text

    def test_patch_prefs_accepts_plain_auth(self, client):
        r = client.patch("/api/prefs", json={"text_scale": 1.5}, headers=AUTH)
        assert r.status_code == 200, r.text

    def test_identity_principal_accepts_plain_auth(self, client):
        r = client.put(
            "/api/identity/principal", json={"display_name": "Ry"}, headers=AUTH
        )
        assert r.status_code == 200, r.text

    def test_lore_confirm_still_needs_step_up(self, client):
        r = client.post("/api/lore/confirm", json={"keys": []}, headers=AUTH)
        assert r.status_code == 403, r.text
        assert "step-up" in r.text

    def test_manifest_matches_the_gates(self, client):
        payload = client.get("/api/manifest", headers=AUTH).json()
        eps = payload["endpoints"]
        rows = (eps["endpoints"] + eps["uncurated"]) if isinstance(eps, dict) else eps
        gate = {(r["method"], r["path"]): r["gate"] for r in rows}
        for key in (
            ("PUT", "/api/prefs"),
            ("PATCH", "/api/prefs"),
            ("PUT", "/api/identity/principal"),
        ):
            assert gate.get(key) == "none", key
        assert gate.get(("POST", "/api/lore/confirm")) == "step-up"


class TestOtherStepUpRoutesUntouched:
    """A route the change list explicitly excludes stays step-up gated —
    proves the relaxation did not spread past the five named routes."""

    def test_identity_agents_still_requires_step_up(self, client):
        r = client.post(
            "/api/identity/agents", json={"agent_id": "bot"}, headers=AUTH
        )
        assert r.status_code == 403
