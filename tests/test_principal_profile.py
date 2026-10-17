"""P0.3: the caller's display name is private runtime state, never
tracked config.

Replaces an earlier working-tree experiment that persisted
``principal.json`` under a hard-coded home path inside the tracked
``config/`` directory. The safe shape: ``PUT /api/identity/principal``
(step-up, persons only) upserts ``display_name`` into ``data/users.json``
and the GET overlays it; agents cannot rename anyone; switching to multi
mode later must not lock the owner out.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.identity import IdentityStore  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    return TestClient(create_app(tmp_path, tmp_path)), tmp_path


H = {"Authorization": "Bearer instancetoken", "X-PW-StepUp": "1"}


def test_default_display_name_is_the_bootstrap_label(client):
    c, _ = client
    r = c.get("/api/identity/principal", headers=H)
    assert r.status_code == 200
    assert r.json()["data"]["display_name"] == "Primary person"


def test_put_persists_under_data_dir_not_config(client):
    c, tmp = client
    r = c.put("/api/identity/principal", json={"display_name": "Ry"},
              headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["display_name"] == "Ry"
    # private runtime state only
    users = json.loads((tmp / "users.json").read_text())
    assert any(u["user_id"] == "primary" and u["display_name"] == "Ry"
               for u in users["users"])
    assert not (tmp / "principal.json").exists()
    repo_config = Path(__file__).parent.parent / "config"
    assert not (repo_config / "principal.json").exists()
    # GET reflects it
    assert c.get("/api/identity/principal",
                 headers=H).json()["data"]["display_name"] == "Ry"


def test_put_requires_auth_and_validates(client):
    c, _ = client
    assert c.put("/api/identity/principal",
                 json={"display_name": "x"}).status_code == 401
    assert c.put("/api/identity/principal", json={"display_name": ""},
                 headers=H).status_code == 400
    assert c.put("/api/identity/principal", json={"display_name": "a" * 81},
                 headers=H).status_code == 400


def test_tokenless_primary_record_never_authenticates_and_survives_mode_switch(tmp_path):
    store = IdentityStore(tmp_path)
    store.set_display_name("primary", "Ry")
    # the record has no credential — nothing can sign in with it
    assert store.match_token("") is None
    assert store.match_token("anything") is None
    # switching to multi mode attaches the instance token instead of
    # returning a tokenless, unusable primary (lockout guard)
    u = store.legacy_primary("instancetoken")
    assert u["display_name"] == "Ry"
    assert store.match_token("instancetoken")["user_id"] == "primary"


def test_agent_cannot_set_display_name(tmp_path, monkeypatch):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    c = TestClient(create_app(tmp_path, tmp_path))
    r = c.post("/api/identity/agents",
               json={"agent_id": "bot", "scopes": ["read", "write"]},
               headers=H)
    assert r.status_code == 200, r.text
    bot = r.json()["data"]["token"]
    r = c.put("/api/identity/principal", json={"display_name": "Evil"},
              headers={"Authorization": f"Bearer {bot}", "X-PW-StepUp": "1"})
    assert r.status_code == 403
