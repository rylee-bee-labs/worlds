"""Live, two-way rooms: change pings, the event stream's hub, read-only views.

A room (Hive Works first) pings ``POST /api/rooms/{id}/changed`` when its
data changes; Worlds forgets what it cached for that room and tells open
screens. ``GET /api/rooms/{id}/views/{name}[/{item}]`` passes a room's own
read-only view through. The transport is ``httpx.MockTransport``.
"""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import rooms  # noqa: E402
from personal_world.rooms import RoomsService  # noqa: E402

ENV = {"PW_ROOMS": "workshop=http://room.test", "PW_ROOM_WORKSHOP_TOKEN_ENV": "T", "T": "tok"}
PROJECTS = {"generated_at": "2026-09-27T01:00:00Z", "projects": [{"id": "proj-vefr", "open": 3}]}


def run(coro):
    return asyncio.run(coro)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _transport(calls, *, views=None):
    views = {"/room/views/projects": PROJECTS} if views is None else views

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path in views:
            v = views[path]
            return v if isinstance(v, httpx.Response) else httpx.Response(200, json=v)
        if path == rooms.ROOM_PATH:
            desc = {"contract": "room/0", "id": "workshop", "name": "W", "icon": "x", "version": "1", "status": "healthy"}
            if "/room/library" in views:
                desc["offers"] = ["library"]
            return httpx.Response(200, json=desc)
        if path in (rooms.CARDS_PATH, rooms.NEEDS_YOU_PATH, rooms.ACTIONS_PATH):
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={})

    return httpx.MockTransport(handle)


class TestChangePings:
    def test_a_ping_drops_the_cache_and_tells_listeners(self):
        calls, clock = [], Clock()
        svc = RoomsService(transport=_transport(calls), clock=clock)
        run(svc.snapshot(ENV))
        assert svc._cache is not None
        q = svc.listen()
        assert run(svc.room_changed("workshop", ENV)) is True
        assert svc._cache is None
        event = q.get_nowait()
        assert event["room"] == "workshop" and event["at"].endswith("Z")

    def test_pings_close_together_fold_into_one(self):
        calls, clock = [], Clock()
        svc = RoomsService(transport=_transport(calls), clock=clock)
        q = svc.listen()
        assert run(svc.room_changed("workshop", ENV)) and run(svc.room_changed("workshop", ENV))
        assert q.qsize() == 1
        clock.t += rooms.PING_MIN_GAP_SECONDS + 0.1
        run(svc.room_changed("workshop", ENV))
        assert q.qsize() == 2

    def test_unknown_or_malformed_rooms_are_refused(self):
        svc = RoomsService(transport=_transport([]), clock=Clock())
        q = svc.listen()
        assert run(svc.room_changed("nope", ENV)) is False
        assert run(svc.room_changed("../x", ENV)) is False
        assert q.empty()

    def test_a_slow_listener_misses_pings_instead_of_blocking(self):
        clock = Clock()
        svc = RoomsService(transport=_transport([]), clock=clock)
        q = svc.listen()
        for _ in range(rooms.LISTENER_QUEUE + 5):
            clock.t += 10
            run(svc.room_changed("workshop", ENV))
        assert q.qsize() == rooms.LISTENER_QUEUE
        svc.unlisten(q)
        assert q not in svc._listeners


class TestViews:
    def test_a_view_passes_through_with_the_rooms_token(self):
        calls = []
        svc = RoomsService(transport=_transport(calls), clock=Clock())
        status, payload = run(svc.view("workshop", "projects", env=ENV))
        assert status == 200 and payload == PROJECTS
        sent = [c for c in calls if c.url.path == "/room/views/projects"][0]
        assert sent.headers["authorization"] == "Bearer tok"

    def test_views_are_cached_until_a_ping(self):
        calls, clock = [], Clock()
        svc = RoomsService(transport=_transport(calls), clock=clock)
        run(svc.view("workshop", "projects", env=ENV))
        run(svc.view("workshop", "projects", env=ENV))
        n = lambda: len([c for c in calls if c.url.path == "/room/views/projects"])  # noqa: E731
        assert n() == 1
        clock.t += 10
        run(svc.room_changed("workshop", ENV))
        run(svc.view("workshop", "projects", env=ENV))
        assert n() == 2

    @pytest.mark.parametrize("name,item", [("../x", None), ("Projects", None), ("projects", "../etc"),
                                           ("projects", "a/b"), ("", None)])
    def test_bad_names_never_reach_the_room(self, name, item):
        calls = []
        svc = RoomsService(transport=_transport(calls), clock=Clock())
        status, _ = run(svc.view("workshop", name, item, env=ENV))
        assert status == 404 and not [c for c in calls if "/room/views" in c.url.path]

    def test_unreadable_views_say_so(self):
        big = httpx.Response(200, content=b"[" + b"1," * (rooms.MAX_VIEW_BYTES // 2) + b"1]")
        views = {"/room/views/big": big, "/room/views/text": httpx.Response(200, text="hi"),
                 "/room/views/err": httpx.Response(500, json={})}
        svc = RoomsService(transport=_transport([], views=views), clock=Clock())
        for name in ("big", "text", "err"):
            assert run(svc.view("workshop", name, env=ENV))[0] == 502
        assert run(svc.view("workshop", "missing", env=ENV))[0] == 404
        assert run(svc.view("nowhere", "projects", env=ENV))[0] == 404


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import personal_world.api as api_mod
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    app = create_app(tmp_path, tmp_path)
    svc = RoomsService(transport=_transport([]), clock=Clock())
    monkeypatch.setattr(api_mod, "_ROOMS", svc)
    return TestClient(app), svc


AUTH = {"Authorization": "Bearer instancetoken"}


class TestRoutes:
    def test_changed_needs_auth_and_a_known_room(self, client):
        c, svc = client
        assert c.post("/api/rooms/workshop/changed", json={}).status_code == 401
        q = svc.listen()
        r = c.post("/api/rooms/workshop/changed", json={}, headers=AUTH)
        assert r.status_code == 200 and r.json()["ok"] is True
        assert q.get_nowait()["room"] == "workshop"
        assert c.post("/api/rooms/nope/changed", json={}, headers=AUTH).status_code == 404

    def test_views_route_envelopes_the_rooms_json(self, client):
        c, _ = client
        assert c.get("/api/rooms/workshop/views/projects").status_code == 401
        r = c.get("/api/rooms/workshop/views/projects", headers=AUTH)
        assert r.status_code == 200 and r.json() == {"ok": True, "data": PROJECTS}
        r = c.get("/api/rooms/workshop/views/nope", headers=AUTH)
        assert r.status_code == 404 and r.json()["ok"] is False

    def test_events_needs_auth(self, client):
        c, _ = client
        assert c.get("/api/rooms/events").status_code == 401


WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 face"


class TestArt:
    def _svc(self, calls, body=WEBP, status=200):
        views = {"/room/art/pip.webp": httpx.Response(status, content=body)}
        return RoomsService(transport=_transport(calls, views=views), clock=Clock())

    def test_a_face_passes_through_with_the_rooms_token_and_is_cached(self):
        calls = []
        svc = self._svc(calls)
        assert run(svc.art("workshop", "pip", ENV)) == WEBP
        assert run(svc.art("workshop", "pip", ENV)) == WEBP
        sent = [c for c in calls if c.url.path == "/room/art/pip.webp"]
        assert len(sent) == 1 and sent[0].headers["authorization"] == "Bearer tok"

    @pytest.mark.parametrize("body", [b"<svg onload=alert(1)>", b"\x89PNG....", b"RIFF" + b"x" * 20])
    def test_only_webp_comes_through(self, body):
        assert run(self._svc([], body=body).art("workshop", "pip", ENV)) is None

    @pytest.mark.parametrize("room,name", [("workshop", "../x"), ("workshop", "Pip"), ("nope", "pip")])
    def test_bad_names_and_rooms_never_reach_a_room(self, room, name):
        calls = []
        assert run(self._svc(calls).art(room, name, ENV)) is None
        assert not [c for c in calls if "/room/art" in c.url.path]


def test_art_route_needs_auth_and_serves_webp(client):
    c, _ = client
    import personal_world.api as api_mod

    views = {"/room/art/pip.webp": httpx.Response(200, content=WEBP)}
    api_mod._ROOMS = RoomsService(transport=_transport([], views=views), clock=Clock())
    assert c.get("/api/rooms/workshop/art/pip.webp").status_code == 401
    r = c.get("/api/rooms/workshop/art/pip.webp", headers=AUTH)
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp" and r.content == WEBP
    assert c.get("/api/rooms/workshop/art/nope.webp", headers=AUTH).status_code == 404


LIB = {"contract": "library/0", "generated_at": "2026-09-27T01:00:00Z",
       "keeper": {"id": "hive-works", "name": "Hive Works", "look": "hive-corporate"},
       "shelves": [{"id": "hive-works", "name": "How Hive Works runs"}],
       "books": [{"id": "b", "shelf": "hive-works", "title": "T", "short": "S.",
                  "pages": [{"kind": "plain", "text": "P"}]}]}


class TestLibraries:
    def _svc(self, lib, calls=None):
        views = {} if lib is None else {"/room/library": lib}
        return RoomsService(transport=_transport([] if calls is None else calls, views=views), clock=Clock())

    def test_a_rooms_library_comes_through_unchanged(self):
        rows = run(self._svc(LIB).libraries(env=ENV))
        assert rows == [{"room": "workshop", "status": "ok", "library": LIB}]

    def test_a_room_without_a_library_has_no_row(self):
        assert run(self._svc(None).libraries(env=ENV)) == []

    def test_a_room_that_doesnt_offer_a_library_is_never_asked(self):
        calls = []
        views = {"/room/library": LIB}

        def handle(request):
            calls.append(request.url.path)
            if request.url.path == rooms.ROOM_PATH:  # descriptor without offers
                return httpx.Response(200, json={"contract": "room/0", "id": "workshop", "name": "W",
                                                 "icon": "x", "version": "1", "status": "healthy"})
            if request.url.path in views:
                return httpx.Response(200, json=views[request.url.path])
            return httpx.Response(200, json=[])
        svc = RoomsService(transport=httpx.MockTransport(handle), clock=Clock())
        assert run(svc.libraries(env=ENV)) == [] and "/room/library" not in calls

    @pytest.mark.parametrize("bad", [
        {**LIB, "contract": "library/9"},
        {**LIB, "books": [{"title": "T", "short": "S", "pages": []}]},
        {**LIB, "books": [{"title": "T", "short": "S", "pages": [{"kind": "secret", "text": "x"}]}]},
        httpx.Response(500, json={}),
        httpx.Response(200, text="not json"),
    ])
    def test_an_unreadable_library_is_said_in_words(self, bad):
        rows = run(self._svc(bad).libraries(env=ENV))
        assert rows[0]["status"] == "unavailable" and "library" not in rows[0]
        assert rows[0]["error"] == "workshop's library couldn't be read."

    def test_a_change_ping_refreshes_the_library(self):
        calls, clock = [], Clock()
        svc = RoomsService(transport=_transport(calls, views={"/room/library": LIB}), clock=clock)
        run(svc.libraries(env=ENV))
        run(svc.libraries(env=ENV))
        n = lambda: len([c for c in calls if c.url.path == "/room/library"])  # noqa: E731
        assert n() == 1
        clock.t += 10
        run(svc.room_changed("workshop", ENV))
        run(svc.libraries(env=ENV))
        assert n() == 2


def test_library_route(client):
    c, _ = client
    import personal_world.api as api_mod

    api_mod._ROOMS = RoomsService(transport=_transport([], views={"/room/library": LIB}), clock=Clock())
    assert c.get("/api/library").status_code == 401
    r = c.get("/api/library", headers=AUTH)
    assert r.status_code == 200 and r.json()["data"][0]["library"]["keeper"]["id"] == "hive-works"


def test_lab_state_reads_through_the_engine_room(client, monkeypatch):
    c, _ = client
    import personal_world.api as api_mod

    packet = {"schema": "lab-lowbw/1", "generated_at": "2026-09-27T00:00:00Z", "rows": {}, "overall_state": "ok"}
    env = {"PW_ROOMS": "engine-room=http://room.test", "PW_ROOM_ENGINE_ROOM_TOKEN_ENV": "T", "T": "tok"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PW_LAB_CLI", "/nonexistent/lab")
    api_mod._ROOMS = RoomsService(transport=_transport([], views={"/room/views/lowbw": packet}), clock=Clock())
    r = c.get("/api/lab/state", headers=AUTH).json()
    assert r["ok"] is True and r["data"]["schema"] == "lab-lowbw/1"
