"""Lore sync: rylee_lore (through the Engine room's view) into the world.

Everything lands as suggested; confirmed lore is never touched; only a
person's own stepped-up request confirms (POST /api/lore/confirm needs a
step-up); gone items are marked, never deleted.
"""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import lore_sync, rooms  # noqa: E402
from personal_world.model import LoreState  # noqa: E402
from personal_world.world import World  # noqa: E402


def _doc(*items, revision="abc1234"):
    return {"source": "rylee_lore", "revision": revision, "skipped": {"pain-research": 18},
            "items": [{"key": k, "text": t, "status": s, "title": "Core", "section": "Accepted",
                       "kind": "claim", "file": "lore/core.md"} for k, t, s in items]}


A = ("lore.core.a", "Rylee decides.", "accepted")
B = ("lore.core.b", "Maybe mornings.", "candidate")


def test_new_items_land_as_suggested_and_a_dry_run_changes_nothing():
    w = World()
    report = lore_sync.plan(w, _doc(A, B))
    assert report["counts"]["new"] == 2 and report["counts"]["accepted_waiting"] == 1 and not w.lore
    lore_sync.apply(w, _doc(A, B))
    assert {lo.state for lo in w.lore.values()} == {LoreState.SUGGESTED}
    assert w.lore["rylee_lore:lore.core.a"].provenance.source == "rylee_lore@abc1234:lore/core.md"


def test_resync_is_idempotent_and_changed_words_update_suggested_only():
    w = World()
    lore_sync.apply(w, _doc(A, B))
    assert lore_sync.plan(w, _doc(A, B))["counts"]["unchanged"] == 2
    lore_sync.confirm(w, ["rylee_lore:lore.core.a"])
    r = lore_sync.apply(w, _doc(("lore.core.a", "Changed words.", "accepted"), ("lore.core.b", "Evenings.", "candidate")))
    assert r["counts"]["confirmed_kept"] == 1 and r["counts"]["changed"] == 1
    assert w.lore["rylee_lore:lore.core.a"].value["text"] == "Rylee decides."  # confirmed never touched
    assert w.lore["rylee_lore:lore.core.b"].value["text"] == "Evenings."


def test_gone_items_are_marked_never_deleted():
    w = World()
    lore_sync.apply(w, _doc(A, B))
    r = lore_sync.apply(w, _doc(A))
    assert r["counts"]["gone"] == 1 and w.lore["rylee_lore:lore.core.b"].value["gone"] is True


def test_accepted_keys_are_the_one_tap_set():
    w = World()
    lore_sync.apply(w, _doc(A, B))
    assert lore_sync.accepted_keys(w) == ["rylee_lore:lore.core.a"]
    assert lore_sync.confirm(w, lore_sync.accepted_keys(w))["confirmed"] == 1
    assert w.lore["rylee_lore:lore.core.a"].state == LoreState.CONFIRMED
    assert lore_sync.accepted_keys(w) == []


# ── The routes, with the Engine room faked ─────────────────────────

TOKEN = "instancetoken"  # pw-safety: synthetic
AUTH = {"Authorization": f"Bearer {TOKEN}"}
STEP = {**AUTH, "X-PW-StepUp": "1"}
ENV = {"PW_ROOMS": "engine-room=http://room.test", "PW_ROOM_ENGINE_ROOM_TOKEN_ENV": "T", "T": "tok"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import personal_world.api as api_mod
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    app = create_app(tmp_path, tmp_path)
    doc = _doc(A, B)

    def handle(request):
        if request.url.path == "/room/views/lore":
            return httpx.Response(200, json=doc)
        if request.url.path == "/room":
            return httpx.Response(200, json={"contract": "room/0", "id": "engine-room", "name": "E",
                                             "icon": "x", "version": "1", "status": "healthy"})
        return httpx.Response(200, json=[])
    monkeypatch.setattr(api_mod, "_ROOMS", rooms.RoomsService(transport=httpx.MockTransport(handle)))
    return TestClient(app)


def test_sync_route_previews_then_imports_then_confirms(client):
    assert client.post("/api/lore/sync", json={"dry_run": True}).status_code == 401
    r = client.post("/api/lore/sync", json={"dry_run": True}, headers=AUTH).json()
    assert r["ok"] and r["data"]["dry_run"] and r["data"]["counts"]["new"] == 2
    assert r["data"]["skipped"] == {"pain-research": 18}
    assert client.get("/api/lore", headers=AUTH).json()["data"]["items"] == []
    client.post("/api/lore/sync", json={}, headers=AUTH)
    listed = client.get("/api/lore", headers=AUTH).json()["data"]
    assert listed["counts"] == {"suggested": 2} and listed["accepted_waiting"] == 1
    c = client.post("/api/lore/confirm", json={"accepted": True}, headers=STEP).json()
    assert c["data"]["confirmed"] == 1
    assert client.get("/api/lore", headers=AUTH).json()["data"]["counts"] == {"suggested": 1, "confirmed": 1}


def test_confirm_needs_step_up(client, monkeypatch):
    """POST /api/lore/confirm changes what Worlds treats as true, so a
    plain authenticated request (no step-up grant, loopback turned off)
    is refused, and nothing is confirmed. Elevated, it passes."""
    import personal_world.api as api_mod

    client.post("/api/lore/sync", json={}, headers=AUTH)
    monkeypatch.setattr(api_mod, "_is_true_loopback", lambda request: False)
    for body in ({"accepted": True}, {"keys": ["anything"]}):
        r = client.post("/api/lore/confirm", json=body, headers=AUTH)
        assert r.status_code == 403 and "step-up" in r.text, r.text
    counts = client.get("/api/lore", headers=AUTH).json()["data"]["counts"]
    assert "confirmed" not in counts
    monkeypatch.setattr(api_mod, "_is_true_loopback", lambda request: True)
    r = client.post("/api/lore/confirm", json={"accepted": True}, headers=AUTH)
    assert r.status_code == 200 and r.json()["data"]["confirmed"] == 1
