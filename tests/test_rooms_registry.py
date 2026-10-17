"""Rooms registry — Worlds reads its room list at runtime (Gap 1).

Project Home's ``GET /api/rooms/registry`` names the estate's rooms; when
``PW_ROOMS_REGISTRY_URL`` is configured Worlds reads that list at snapshot
time (cached 60 s), so adding or removing a room needs no Worlds restart.

These tests pin:

* registry ok → its enabled rooms are used, report ``source: registry`` /
  ``status: ok``;
* disabled entries are returned by the registry but skipped here;
* malformed entries are dropped, never guessed;
* the token is read through the ``token_env`` NAME indirection and never
  appears in a row or the report;
* registry down → last-known-good, honestly reported;
* registry down with nothing cached → ``PW_ROOMS`` env fallback;
* not configured → env (today's behaviour);
* an unsupported contract (registry entry or the room's own descriptor)
  is ``incompatible`` — never healthy, cards/needs never counted;
* per-refresh add/remove with the 60 s registry cache.

The transport is ``httpx.MockTransport``; no network is touched.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.rooms import RoomsService  # noqa: E402

REGISTRY_URL = "https://registry.test/api/rooms/registry"

DESCRIPTOR = {
    "contract": "room/0",
    "id": "studio",
    "name": "Studio",
    "icon": "book",
    "version": "1.0.0",
    "commit": "a1b2c3d",
    "status": "healthy",
    "updated_at": "2026-09-25T13:05:48Z",
}

NEEDS = [
    {
        "id": "need-1",
        "title": "Confirm the transfer",
        "why": "waiting",
        "actions": [],
        "created_at": "2026-09-25T12:30:00Z",
    }
]

# Synthetic, short, never a real credential.
TOKEN_VALUE = "tok-abc"
TOKEN_ENV_NAME = "PW_ROOM_WORKSHOP_TOKEN"


def run(coro):
    return asyncio.run(coro)


def _entry(
    room_id,
    *,
    base_url="http://room.test",
    contract="room/0",
    token_env=None,
    insecure_tls=False,
    enabled=True,
    name=None,
    public_url=None,
):
    return {
        "id": room_id,
        "name": name or room_id.title(),
        "base_url": base_url,
        "contract": contract,
        "token_env": token_env,
        "insecure_tls": insecure_tls,
        "enabled": enabled,
        "public_url": public_url,
    }


def _registry(rooms, *, updated_at="2026-09-25T12:00:00Z", tokens=None):
    def handle(request: httpx.Request) -> httpx.Response:
        if tokens is not None:
            tokens.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"updated_at": updated_at, "rooms": rooms})

    return handle


def _room(descriptor=None, needs=None, tokens=None, calls=None):
    descriptor = descriptor or (lambda: httpx.Response(200, json=DESCRIPTOR))
    needs = needs or (lambda: httpx.Response(200, json=NEEDS))

    def handle(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        if tokens is not None:
            tokens.append(request.headers.get("authorization"))
        if request.url.path == "/room":
            return descriptor()
        if request.url.path == "/room/cards":
            return httpx.Response(200, json=[])
        if request.url.path == "/room/needs-you":
            return needs()
        return httpx.Response(404, json={"detail": "unknown"})

    return handle


def _transport(*, registry, room):
    """Route ``registry.test`` to the registry handler, everything else to
    the room handler. ``None`` means that leg is down."""

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.test":
            if registry is None:
                raise httpx.ConnectError("registry down")
            return registry(request)
        if room is None:
            raise httpx.ConnectError("room down")
        return room(request)

    return httpx.MockTransport(handle)


class TestRegistryResolution:
    def test_registry_ok_uses_enabled_rooms(self):
        reg_tokens: list = []
        svc = RoomsService(
            transport=_transport(
                registry=_registry(
                    [_entry("workshop"), _entry("studio")], tokens=reg_tokens
                ),
                room=_room(),
            )
        )
        rows = run(svc.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        assert [r["id"] for r in rows] == ["workshop", "studio"]
        report = svc.registry_report()
        assert report["source"] == "registry"
        assert report["status"] == "ok"
        assert report["checked_at"]
        assert report["error"] is None
        # No token configured → no Authorization header to the registry.
        assert reg_tokens == [None]

    def test_disabled_entries_are_returned_but_skipped(self):
        svc = RoomsService(
            transport=_transport(
                registry=_registry(
                    [_entry("workshop"), _entry("studio", enabled=False)]
                ),
                room=_room(),
            )
        )
        rows = run(svc.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        assert [r["id"] for r in rows] == ["workshop"]
        # A deliberately-disabled entry is not a malformed one.
        assert svc.registry_report()["dropped"] == 0

    def test_malformed_entries_are_dropped_never_guessed(self):
        rooms = [
            _entry("workshop"),
            _entry("BAD ID"),
            _entry("ftp-room", base_url="ftp://room.test"),
            _entry("no-url", base_url="not-a-url"),
            "not-an-object",
            {"id": "no-contract", "base_url": "http://room.test"},
        ]
        svc = RoomsService(
            transport=_transport(registry=_registry(rooms), room=_room())
        )
        rows = run(svc.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        assert [r["id"] for r in rows] == ["workshop"]
        assert svc.registry_report()["dropped"] == 5

    def test_token_env_indirection_value_never_returned(self):
        room_tokens: list = []
        svc = RoomsService(
            transport=_transport(
                registry=_registry(
                    [_entry("workshop", token_env=TOKEN_ENV_NAME)]
                ),
                room=_room(tokens=room_tokens),
            )
        )
        rows = run(
            svc.snapshot(
                {
                    "PW_ROOMS_REGISTRY_URL": REGISTRY_URL,
                    TOKEN_ENV_NAME: TOKEN_VALUE,
                }
            )
        )
        assert room_tokens and all(
            t == f"Bearer {TOKEN_VALUE}" for t in room_tokens
        )
        blob = json.dumps({"rows": rows, "registry": svc.registry_report()})
        assert TOKEN_VALUE not in blob  # the value never leaves the header
        assert TOKEN_ENV_NAME not in blob  # only its NAME is ever known here

    def test_registry_bearer_token_is_read_through_the_env_name(self):
        reg_tokens: list = []
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_entry("workshop")], tokens=reg_tokens),
                room=_room(),
            )
        )
        run(
            svc.snapshot(
                {
                    "PW_ROOMS_REGISTRY_URL": REGISTRY_URL,
                    "PW_ROOMS_REGISTRY_TOKEN_ENV": "PW_REGISTRY_TOKEN",
                    "PW_REGISTRY_TOKEN": TOKEN_VALUE,
                }
            )
        )
        assert reg_tokens == [f"Bearer {TOKEN_VALUE}"]
        assert TOKEN_VALUE not in json.dumps(svc.registry_report())


class TestRegistryFallback:
    def test_registry_down_uses_last_known_good(self, tmp_path):
        state = tmp_path / "rooms-registry.json"
        up = RoomsService(
            transport=_transport(
                registry=_registry([_entry("workshop")]), room=_room()
            ),
            registry_state_path=state,
        )
        first = run(up.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        assert [r["id"] for r in first] == ["workshop"]
        assert state.exists()

        down = RoomsService(
            transport=_transport(registry=None, room=_room()),
            registry_state_path=state,
        )
        rows = run(down.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        assert [r["id"] for r in rows] == ["workshop"]
        assert rows[0]["reachable"] is True  # the room itself is up
        report = down.registry_report()
        assert report["source"] == "last_known_good"
        assert report["status"] == "unreachable"
        assert report["error"] == "connect error"
        assert report["updated_at"] == "2026-09-25T12:00:00Z"

    def test_registry_down_without_cache_falls_back_to_env(self):
        env = {
            "PW_ROOMS_REGISTRY_URL": REGISTRY_URL,
            "PW_ROOMS": "workshop=http://room.test",
        }
        svc = RoomsService(transport=_transport(registry=None, room=_room()))
        rows = run(svc.snapshot(env))
        assert [r["id"] for r in rows] == ["workshop"]
        report = svc.registry_report()
        assert report["source"] == "env"
        assert report["status"] == "unreachable"
        assert report["error"] == "connect error"

    def test_not_configured_falls_back_to_env(self):
        svc = RoomsService(transport=_transport(registry=None, room=_room()))
        rows = run(svc.snapshot({"PW_ROOMS": "workshop=http://room.test"}))
        assert [r["id"] for r in rows] == ["workshop"]
        report = svc.registry_report()
        assert report["source"] == "env"
        assert report["status"] == "not_configured"
        assert report["error"] is None

    def test_corrupt_last_known_good_file_never_fabricates_rooms(self, tmp_path):
        state = tmp_path / "rooms-registry.json"
        state.write_text("{not json")
        svc = RoomsService(
            transport=_transport(registry=None, room=_room()),
            registry_state_path=state,
        )
        rows = run(
            svc.snapshot(
                {
                    "PW_ROOMS_REGISTRY_URL": REGISTRY_URL,
                    "PW_ROOMS": "workshop=http://room.test",
                }
            )
        )
        assert [r["id"] for r in rows] == ["workshop"]
        assert svc.registry_report()["source"] == "env"


class TestRegistryCompatibility:
    def test_incompatible_registry_entry_is_not_loaded(self):
        calls: list = []
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_entry("workshop", contract="room/9")]),
                room=_room(calls=calls),
            )
        )
        row = run(svc.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))[0]
        assert row["status"] == "incompatible"
        assert row["status"] != "healthy"
        assert row["reachable"] is False
        assert "room/9" in row["error"]
        assert row["needs_you"] == []
        assert row["cards"] == []
        assert calls == []  # never even probed

    def test_incompatible_descriptor_is_incompatible_and_needs_not_counted(self):
        bad = dict(DESCRIPTOR, contract="room/9")
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_entry("workshop")]),
                room=_room(descriptor=lambda: httpx.Response(200, json=bad)),
            )
        )
        row = run(svc.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))[0]
        assert row["reachable"] is True  # it answered
        assert row["room"] is None
        assert row["status"] == "incompatible"
        assert "room/9" in row["error"]
        assert row["needs_you"] == []
        assert row["cards"] == []


class TestRegistryCache:
    def test_registry_cache_60s_and_per_refresh_add_remove(self):
        clock = {"t": 1000.0}
        current = {"rooms": [_entry("workshop")]}
        svc = RoomsService(
            transport=_transport(
                registry=lambda request: httpx.Response(
                    200,
                    json={
                        "updated_at": "2026-09-25T12:00:00Z",
                        "rooms": current["rooms"],
                    },
                ),
                room=_room(),
            ),
            clock=lambda: clock["t"],
        )
        env = {"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}
        assert [r["id"] for r in run(svc.snapshot(env))] == ["workshop"]

        # Registry changed, but the 60 s registry cache is still warm.
        current["rooms"] = [_entry("workshop"), _entry("studio")]
        clock["t"] += 20
        assert [r["id"] for r in run(svc.snapshot(env))] == ["workshop"]

        # Past the registry TTL: the added room appears, no restart.
        clock["t"] += 50
        assert [r["id"] for r in run(svc.snapshot(env))] == ["workshop", "studio"]

        # A removal takes effect the same way on the next refresh.
        current["rooms"] = [_entry("studio")]
        clock["t"] += 70
        assert [r["id"] for r in run(svc.snapshot(env))] == ["studio"]


class TestRegistryPublicUrl:
    def test_public_url_is_parsed_and_surfaced_on_the_row(self):
        svc = RoomsService(
            transport=_transport(
                registry=_registry(
                    [_entry("workshop", public_url="https://workshop.example")]
                ),
                room=_room(),
            )
        )
        row = run(svc.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))[0]
        assert row["base_url"] == "http://room.test"
        assert row["public_url"] == "https://workshop.example"

    def test_absent_public_url_is_null(self):
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_entry("workshop")]), room=_room()
            )
        )
        row = run(svc.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))[0]
        assert row["public_url"] is None

    def test_invalid_public_url_is_dropped_but_the_entry_is_kept(self):
        entries = [
            _entry("userinfo", public_url="https://user:pass@room.test"),
            _entry("ftp", public_url="ftp://room.test"),
            _entry("relative", public_url="/room"),
            _entry("non-string", public_url=8940),
            _entry("blank", public_url=""),
        ]
        svc = RoomsService(
            transport=_transport(registry=_registry(entries), room=_room())
        )
        rows = run(svc.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        assert [r["id"] for r in rows] == [
            "userinfo",
            "ftp",
            "relative",
            "non-string",
            "blank",
        ]
        assert all(r["public_url"] is None for r in rows)
        assert svc.registry_report()["dropped"] == 0

    def test_public_url_survives_last_known_good(self, tmp_path):
        state = tmp_path / "rooms-registry.json"
        up = RoomsService(
            transport=_transport(
                registry=_registry(
                    [_entry("workshop", public_url="https://workshop.example")]
                ),
                room=_room(),
            ),
            registry_state_path=state,
        )
        run(up.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        assert state.exists()

        down = RoomsService(
            transport=_transport(registry=None, room=_room()),
            registry_state_path=state,
        )
        row = run(down.snapshot({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))[0]
        assert row["public_url"] == "https://workshop.example"
