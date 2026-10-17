"""Issue #8 phases 2/3: provisioning, agent principals, cross-user isolation.

Proves the two-user acceptance core on the identity seam:
- admin can provision another person without touching internals
- both users sign in with their own tokens
- per-user world/journal/prefs isolation (no cross-profile leak)
- agents are owned principals with narrow scopes
- disabling a user/agent removes access immediately
- single mode stays byte-identical (legacy gate untouched)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402


def _mk(tmp_path, monkeypatch):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    app = create_app(tmp_path, tmp_path)
    return TestClient(app)


def _h(tok):
    return {"Authorization": f"Bearer {tok}",
            "X-PW-StepUp": "1"}


def _admin_provisions_user(c, user_id="second"):
    r = c.post("/api/identity/users",
               json={"user_id": user_id, "display_name": "Second"},
               headers=_h("instancetoken"))
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


def test_admin_provisions_user_without_internals(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok = _admin_provisions_user(c)
    assert tok
    # second user can now call the API with their own token
    r = c.get("/api/prefs", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text


def test_two_users_full_isolation(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok_b = _admin_provisions_user(c, "beta")
    # alpha (bootstrap "primary" owns the instance token) writes a pref
    r = c.put("/api/prefs",
              json={"text_scale": 1.25},
              headers=_h("instancetoken"))
    assert r.status_code == 200, r.text
    # beta's world must NOT see alpha's text_scale
    r2 = c.get("/api/prefs", headers={"Authorization": f"Bearer {tok_b}"})
    assert r2.status_code == 200
    got = r2.json()["data"]
    assert got.get("text_scale") in (None, 1.0)


def test_journal_isolation_between_users(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok_b = _admin_provisions_user(c, "beta")
    c.post("/api/journal", json={"text": "alpha private note"},
           headers=_h("instancetoken"))
    r = c.get("/api/journal",
              headers={"Authorization": f"Bearer {tok_b}"})
    texts = [e.get("summary") for e in r.json()["data"]]
    assert "alpha private note" not in texts


def test_agent_owned_principal_scoped(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    r = c.post("/api/identity/agents",
               json={"agent_id": "loreling",
                     "scopes": ["read", "journal"]},
               headers=_h("instancetoken"))
    assert r.status_code == 200, r.text
    atok = r.json()["data"]["token"]
    p = c.get("/api/identity/agents",
              headers={"Authorization": f"Bearer {atok}"}).json()["data"]
    me = [a for a in p if a["user_id"] == "loreling"]
    assert me and me[0]["owner_id"] == "primary"
    assert set(me[0]["scopes"]) == {"read", "journal"}
    # agents CAN read shared-general surfaces
    assert c.get("/api/status",
                 headers={"Authorization": f"Bearer {atok}"}).status_code == 200


def test_agent_cannot_step_up_writes(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    r = c.post("/api/identity/agents",
               json={"agent_id": "loreling", "scopes": ["write"]},
               headers=_h("instancetoken"))
    atok = r.json()["data"]["token"]
    # step-up write is a person-side action: agents must be refused
    r2 = c.put("/api/prefs", json={"text_scale": 2.0},
               headers={"Authorization": f"Bearer {atok}",
                        "X-PW-StepUp": "1"})
    assert r2.status_code in (403, 409)


def test_disabled_user_loses_access(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok_b = _admin_provisions_user(c, "beta")
    assert c.get("/api/prefs",
                 headers={"Authorization": f"Bearer {tok_b}"}).status_code == 200
    r = c.delete("/api/identity/users/beta", headers=_h("instancetoken"))
    assert r.status_code == 200
    assert c.get("/api/prefs",
                 headers={"Authorization": f"Bearer {tok_b}"}).status_code == 401


def test_disabled_agent_loses_access(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    r = c.post("/api/identity/agents", json={"agent_id": "tmpbot"},
               headers=_h("instancetoken"))
    atok = r.json()["data"]["token"]
    d = c.delete("/api/identity/agents/tmpbot", headers=_h("instancetoken"))
    assert d.status_code == 200
    assert c.get("/api/status",
                 headers={"Authorization": f"Bearer {atok}"}).status_code == 401


def test_non_admin_cannot_provision(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok_b = _admin_provisions_user(c, "beta")
    r = c.post("/api/identity/users",
               json={"user_id": "sneaky"},
               headers=_h(tok_b))
    assert r.status_code == 403


def test_single_mode_untouched(tmp_path, monkeypatch):
    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.delenv("PW_IDENTITY_MODE", raising=False)
    from personal_world.api import create_app
    c = TestClient(create_app(tmp_path, tmp_path))
    # legacy token still opens the door, no users route write needed
    assert c.get("/api/prefs",
                 headers={"Authorization": "Bearer instancetoken"}).status_code == 200
