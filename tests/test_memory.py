"""Remember, recall, Later: one place, nothing to chase."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import memory  # noqa: E402


def test_recall_needs_every_word_and_ranks_newest_best_first():
    src = [{"text": "the hidden door needs the weird lantern", "when": "2026-09-27", "where": "Journal"},
           {"text": "a lantern for the porch", "when": "2026-09-28", "where": "Later shelf"},
           {"text": "nothing here", "when": "2026-09-29", "where": "Journal"}]
    got = memory.recall("lantern door", src)
    assert [g["where"] for g in got] == ["Journal"]
    assert [g["when"] for g in memory.recall("lantern", src)] == ["2026-09-28", "2026-09-27"]
    assert memory.recall("  ", src) == []


def test_later_shelf_keeps_three_in_progress_and_never_drops_one():
    d = {"items": []}
    ids = [memory.add_later(d, f"idea {n}")["id"] for n in range(5)]
    for i in ids[:3]:
        assert memory.move(d, i, "doing")[0]
    ok, said, _ = memory.move(d, ids[3], "doing")
    assert not ok and "Three things are already in progress" in said
    assert memory.move(d, ids[0], "done")[0] and memory.move(d, ids[3], "doing")[0]
    assert len(d["items"]) == 5


TOKEN = "instancetoken"  # pw-safety: synthetic
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    return TestClient(create_app(tmp_path, tmp_path))


def test_remember_then_recall_then_later(client):
    assert client.post("/api/remember", json={"text": "x"}).status_code == 401
    assert client.post("/api/remember", headers=AUTH, json={"text": "The lantern opens the hidden door"}).json()["data"]["kept"] == "journal"
    assert client.post("/api/remember", headers=AUTH, json={"text": "Paint the lantern gold", "later": True}).json()["data"]["kept"] == "later"
    res = client.get("/api/recall", params={"q": "lantern"}, headers=AUTH).json()["data"]["results"]
    assert {r["where"] for r in res} == {"Journal", "Later shelf"}
    shelf = client.get("/api/later", headers=AUTH).json()["data"]
    item = shelf["later"][0]
    assert client.post(f"/api/later/{item['id']}", headers=AUTH, json={"to": "doing"}).json()["data"]["said"] == "Started."
    assert client.post("/api/later/nope", headers=AUTH, json={"to": "doing"}).status_code == 404
