"""The sticker album (stickers/0): what shows, what stays hidden, who may
report a find, and the moments that earn Worlds stickers."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import stickers  # noqa: E402

OWNER = "stickers-owner-token"  # pw-safety: synthetic
VEFR_KEY = "stickers-vefr-key"  # pw-safety: synthetic
H = {"Authorization": f"Bearer {OWNER}"}
V = {"Authorization": f"Bearer {VEFR_KEY}"}


@pytest.fixture(params=["single", "multi"])
def client(tmp_path, monkeypatch, request):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", OWNER)
    monkeypatch.setenv("PW_STICKERS_TOKENS", f"vefr={VEFR_KEY}")
    monkeypatch.setenv("PW_IDENTITY_MODE", request.param)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("PW_ROOMS", raising=False)
    monkeypatch.delenv("PW_ROOMS_REGISTRY_URL", raising=False)
    return TestClient(create_app(tmp_path, tmp_path))


def _worlds(c):
    pages = c.get("/api/stickers", headers=H).json()["data"]["pages"]
    return next(p for p in pages if p["app"] == "worlds")


def test_album_shows_open_riddles_as_riddles_and_hides_secrets(client):
    page = _worlds(client)
    by = {s["id"]: s for s in page["stickers"]}
    assert by["first-light"]["found"] is True  # opening the album is the first light
    assert by["pen-to-paper"]["name"] == "Pen to Paper" and by["pen-to-paper"]["found"] is False
    assert "name" not in by["cover-to-cover"] and by["cover-to-cover"]["riddle"]
    assert "sol-hi" not in by and page["secrets_remain"] is True  # secrets never listed
    assert "one-more-door" not in by  # whispered until All the Doors is found


def test_a_person_reports_a_worlds_moment_and_it_shows(client):
    r = client.post("/api/stickers/found", json={"app": "worlds", "sticker": "sol-hi"}, headers=H)
    assert r.status_code == 200 and r.json()["data"]["new"] is True
    again = client.post("/api/stickers/found", json={"app": "worlds", "sticker": "sol-hi"}, headers=H)
    assert again.json()["data"]["new"] is False  # found is forever; repeats harmless
    by = {s["id"]: s for s in _worlds(client)["stickers"]}
    assert by["sol-hi"]["found"] is True and by["sol-hi"]["name"] == "Sol Says Hi"


@pytest.mark.parametrize("body", [
    {"app": "worlds", "sticker": "sticker-room"},   # earned only from other stickers
    {"app": "worlds", "sticker": "know-thyself"},   # earned only from confirmed lore
    {"app": "vefr", "sticker": "gatekeeper"},       # a person can't report another app's sticker
    {"app": "worlds", "sticker": "no-such-one"},
])
def test_a_person_cannot_hand_out_earned_or_foreign_stickers(client, body):
    assert client.post("/api/stickers/found", json=body, headers=H).status_code == 422


def test_an_apps_key_reports_only_its_own_stickers_and_reaches_nothing_else(client):
    ok = client.post("/api/stickers/found", json={"app": "vefr", "sticker": "gatekeeper", "context": "the lantern door"}, headers=V)
    assert ok.status_code == 200
    assert client.post("/api/stickers/found", json={"app": "hive-works", "sticker": "x"}, headers=V).status_code == 403
    for path in ("/api/stickers", "/api/me", "/api/journal", "/api/learning"):
        assert client.get(path, headers=V).status_code == 403, path


def test_remember_earns_tied_a_string(client):
    r = client.post("/api/remember", json={"text": "call the vet"}, headers=H)
    assert r.status_code == 200
    by = {s["id"]: s for s in _worlds(client)["stickers"]}
    assert by["tied-a-string"]["found"] is True


def test_place_needs_a_found_sticker_and_clamps(client):
    assert client.post("/api/stickers/place", json={"app": "worlds", "sticker": "pen-to-paper", "x": 0.5, "y": 0.5}, headers=H).status_code == 404
    _worlds(client)  # first-light is found on first open
    r = client.post("/api/stickers/place", json={"app": "worlds", "sticker": "first-light", "x": 2, "y": -1, "r": 90}, headers=H)
    assert r.json()["data"]["placed"] == {"x": 1.0, "y": 0.0, "r": 30.0}


def test_cascades_and_whispers():
    data = {"found": {}, "placed": {}}
    for i in range(12):
        stickers.find(data, "vefr", f"s{i}")
    assert "worlds:sticker-room" in data["found"]
    stickers.find(data, "hive-works", "a")
    stickers.find(data, "worlds", "pen-to-paper")
    assert "worlds:constellation" in data["found"]  # three different apps
    stickers.find(data, "worlds", "all-doors")
    shown = {s["id"] for s in stickers.page("worlds", "Worlds", None, stickers.WORLDS, 0, data)["stickers"]}
    assert "one-more-door" in shown  # its neighbour is found, so the riddle appears



def test_a_wrapped_view_is_read_like_a_bare_one():
    """Hive Works' views wrap their document ({generated_at, stickers: {...}})."""
    import asyncio

    from personal_world import rooms as rooms_mod

    svc = rooms_mod.RoomsService.__new__(rooms_mod.RoomsService)
    cfg = rooms_mod.RoomConfig(id="hive-works", base_url="http://room.test")
    wrapped = {"generated_at": "2026-09-27T12:00:00Z",
               "stickers": {"contract": "stickers/0", "app": "hive-works", "stickers": [{"id": "a", "kind": "open"}]}}

    async def configs(env):
        return [cfg], None

    async def snapshot(env=None):
        return [{"id": "hive-works", "room": {"offers": ["views", "stickers"]}}]

    async def fetch(config, path, name, principal):
        return 200, wrapped

    svc._resolve_configs, svc.snapshot, svc._fetch_json = configs, snapshot, fetch
    rows = asyncio.run(svc.sticker_sets(None, env={}))
    assert rows[0]["status"] == "ok" and rows[0]["set"]["contract"] == "stickers/0"


def test_a_room_serving_stickers_as_a_view_is_asked_too():
    """VEFR lists only "views" (the room schema has no "stickers" offer yet)."""
    import asyncio

    from personal_world import rooms as rooms_mod

    svc = rooms_mod.RoomsService.__new__(rooms_mod.RoomsService)
    cfg = rooms_mod.RoomConfig(id="vefr", base_url="http://room.test")
    bare = {"contract": "stickers/0", "app": "vefr", "stickers": [{"id": "hello-studio", "kind": "open"}], "secrets": 18}

    async def configs(env):
        return [cfg], None

    async def snapshot(env=None):
        return [{"id": "vefr", "room": {"offers": ["views", "art", "library"]}}]

    async def fetch(config, path, name, principal):
        return 200, bare

    svc._resolve_configs, svc.snapshot, svc._fetch_json = configs, snapshot, fetch
    rows = asyncio.run(svc.sticker_sets(None, env={}))
    assert rows and rows[0]["room"] == "vefr" and rows[0]["status"] == "ok"
