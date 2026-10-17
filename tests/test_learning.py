"""Teach while building: first → again (with where it was first met) →
familiar; plain words means off; occasional means one tip a day."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import learning  # noqa: E402


def test_first_again_familiar_and_the_first_context_travels():
    d = learning.load(Path("/nonexistent"))
    assert learning.encounter(d, "gating", "vefr", "the hidden door that needed the lantern")["stage"] == "first"
    again = learning.encounter(d, "gating", "memomancer", "an ability after talking to Mira")
    assert again == {"concept": "gating", "stage": "again",
                     "first_context": "the hidden door that needed the lantern", "first_project": "vefr"}
    learning.encounter(d, "gating", "vefr", "x")
    assert learning.encounter(d, "gating", "vefr", "y")["stage"] == "familiar"
    assert d["concepts"]["gating"]["projects"] == ["vefr", "memomancer"]


def test_got_it_twice_makes_it_familiar():
    d = learning.load(Path("/nonexistent"))
    learning.encounter(d, "affordance", "worlds", "a button that looks pressable")
    learning.got_it(d, "affordance")
    assert learning.got_it(d, "affordance") == "familiar"


def test_plain_words_means_off_and_occasional_means_one_a_day():
    d = learning.load(Path("/nonexistent"))
    d["mode"] = "plain"
    assert learning.encounter(d, "gating", "vefr", "x")["stage"] == "off"
    d2 = learning.load(Path("/nonexistent"))
    d2["mode"] = "occasional"
    assert learning.encounter(d2, "gating", "vefr", "x")["stage"] == "first"
    assert learning.encounter(d2, "signposting", "vefr", "x")["stage"] == "off"


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


def test_routes(client):
    assert client.post("/api/learning/encounter", json={}).status_code == 401
    r = client.post("/api/learning/encounter", headers=AUTH,
                    json={"concept": "gating", "project": "vefr", "context": "the hidden door"}).json()
    assert r["data"]["stage"] == "first"
    assert client.post("/api/learning/encounter", headers=AUTH,
                       json={"concept": "../x", "project": "vefr"}).status_code == 422
    assert client.put("/api/learning/mode", headers=AUTH, json={"mode": "loud"}).status_code == 422
    client.put("/api/learning/mode", headers=AUTH, json={"mode": "occasional"})
    view = client.get("/api/learning", headers=AUTH).json()["data"]
    assert view["mode"] == "occasional" and view["concepts"]["gating"]["stage"] == "again"
    assert client.post("/api/learning/got-it", headers=AUTH, json={"concept": "gating"}).json()["data"]["stage"] == "again"
