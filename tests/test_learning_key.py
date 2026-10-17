"""A project's learning key (PW_LEARNING_TOKEN, single and multi mode) writes the
owner's learning memory and reaches nothing else — not even reads."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

OWNER = "learnkey-owner-token"  # pw-safety: synthetic
KEY = "learnkey-project-token"  # pw-safety: synthetic


@pytest.fixture(params=["single", "multi"])
def client(tmp_path, monkeypatch, request):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", OWNER)
    monkeypatch.setenv("PW_LEARNING_TOKEN", KEY)
    monkeypatch.setenv("PW_IDENTITY_MODE", request.param)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    return TestClient(create_app(tmp_path, tmp_path))


def test_learning_key_writes_the_owners_learning_memory(client):
    key = {"Authorization": f"Bearer {KEY}"}
    r = client.post(
        "/api/learning/encounter",
        json={"concept": "gating", "project": "vefr", "context": "the hidden door"},
        headers=key,
    )
    assert r.status_code == 200, r.text
    assert client.post("/api/learning/got-it", json={"concept": "gating"}, headers=key).status_code == 200
    assert client.put("/api/learning/mode", json={"mode": "occasional"}, headers=key).status_code == 200
    # The owner sees it: it's their memory, not the key's.
    owner = client.get("/api/learning", headers={"Authorization": f"Bearer {OWNER}"}).json()["data"]
    assert "gating" in owner["concepts"] and owner["mode"] == "occasional"


@pytest.mark.parametrize(
    "method,path",
    [("GET", "/api/me"), ("GET", "/api/journal"), ("GET", "/api/rooms"), ("GET", "/api/lore"),
     ("POST", "/api/journal"), ("GET", "/api/records")],
)
def test_learning_key_reaches_nothing_else(client, method, path):
    r = client.request(method, path, headers={"Authorization": f"Bearer {KEY}"}, json={"text": "x"})
    assert r.status_code == 403, (path, r.status_code)


def test_without_the_setting_the_key_is_just_wrong(tmp_path, monkeypatch):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", OWNER)
    monkeypatch.delenv("PW_LEARNING_TOKEN", raising=False)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    c = TestClient(create_app(tmp_path, tmp_path))
    assert c.get("/api/learning", headers={"Authorization": f"Bearer {KEY}"}).status_code == 401
