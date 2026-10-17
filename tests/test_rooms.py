"""Rooms — the front door renders other small backends (contract: room/0).

These tests pin the honesty floor of ``src/personal_world/rooms.py`` and
``GET /api/rooms``:

* a reachable room carries its descriptor, status, and needs-you;
* an unreachable room is ``reachable: false``, ``room: null``, status
  ``unreachable`` — never ``healthy``;
* a timeout and malformed JSON are named, never raised;
* a bearer token is sent only when the room configured one (via the
  ``PW_ROOM_<ID>_TOKEN_ENV`` indirection), and never appears in a row;
* ``last_seen``/``last_status`` survive a later outage and a restart
  (persisted to the state file when one is configured);
* the snapshot is cached for 15 s;
* the route requires authentication.

The transport is ``httpx.MockTransport`` — the same httpx the repo
already uses for its TestClient and OIDC tests; no network is touched.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import rooms  # noqa: E402
from personal_world.rooms import RoomsService, parse_rooms  # noqa: E402

DESCRIPTOR = {
    "contract": "room/0",
    "id": "studio",
    "name": "Studio",
    "icon": "book",
    "voice": "dry and precise",
    "version": "1.2.0",
    "commit": "a1b2c3d",
    "status": "healthy",
    "updated_at": "2026-09-25T13:05:48Z",
}

NEEDS = [
    {
        "id": "need-1",
        "title": "Confirm the transfer",
        "why": "A withdrawal above the usual threshold is waiting.",
        "actions": ["confirm-transfer"],
        "created_at": "2026-09-25T12:30:00Z",
    }
]

# Synthetic, short, never a real credential. Not 24+ chars, so it can
# never look like an embedded secret to the public-safety scanner.
TOKEN_VALUE = "tok-abc"


def run(coro):
    return asyncio.run(coro)


def _handler(*, descriptor=None, needs=None, cards=None, calls=None, tokens=None):
    """A MockTransport handler for one room's three read endpoints."""

    def handle(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        if tokens is not None:
            tokens.append(request.headers.get("authorization"))
        if request.url.path == rooms.ROOM_PATH:
            if descriptor is None:
                return httpx.Response(500, json={"detail": "no"})
            return descriptor()
        if request.url.path == rooms.CARDS_PATH:
            # Absent cards are simply no cards — a valid, honest room.
            return cards() if cards is not None else httpx.Response(200, json=[])
        if request.url.path == rooms.NEEDS_YOU_PATH:
            if needs is None:
                return httpx.Response(500, json={"detail": "no"})
            return needs()
        return httpx.Response(404, json={"detail": "unknown"})

    return handle


def _ok_descriptor():
    return httpx.Response(200, json=DESCRIPTOR)


def _ok_needs():
    return httpx.Response(200, json=NEEDS)


# ── Configuration ────────────────────────────────────────────────────


class TestParseRooms:
    def test_parses_id_and_base_url_list(self):
        cfgs = parse_rooms({"PW_ROOMS": "studio=http://127.0.0.1:8940, workshop=https://127.0.0.1:8961"})
        assert [(c.id, c.base_url) for c in cfgs] == [
            ("studio", "http://127.0.0.1:8940"),
            ("workshop", "https://127.0.0.1:8961"),
        ]
        assert all(c.invalid_reason is None for c in cfgs)

    def test_token_env_indirection_reads_the_named_var(self):
        cfgs = parse_rooms(
            {
                "PW_ROOMS": "studio=http://127.0.0.1:8940",
                "PW_ROOM_STUDIO_TOKEN_ENV": "PW_STUDIO_TOKEN",
                "PW_STUDIO_TOKEN": TOKEN_VALUE,
            }
        )
        assert cfgs[0].token == TOKEN_VALUE
        # A missing named var means no token, not a crash.
        assert parse_rooms({"PW_ROOMS": "studio=http://x.test"})[0].token is None

    def test_owner_token_env_indirection_reads_the_named_var(self):
        cfgs = parse_rooms(
            {
                "PW_ROOMS": "studio=http://127.0.0.1:8940",
                "PW_ROOM_STUDIO_OWNER_TOKEN_ENV": "PW_STUDIO_OWNER_TOKEN",
                "PW_STUDIO_OWNER_TOKEN": "owner-tok",
            }
        )
        assert cfgs[0].owner_token == "owner-tok"
        assert cfgs[0].owner_token_env == "PW_STUDIO_OWNER_TOKEN"
        # No owner token configured — most rooms today — is None, not a
        # crash, and independent of the room's ordinary token.
        cfgs = parse_rooms({"PW_ROOMS": "studio=http://x.test"})
        assert cfgs[0].owner_token is None
        assert cfgs[0].owner_token_env is None

    def test_insecure_tls_flag(self):
        cfgs = parse_rooms(
            {
                "PW_ROOMS": "studio=https://room.test:8940",
                "PW_ROOM_STUDIO_INSECURE_TLS": "1",
            }
        )
        assert cfgs[0].insecure_tls is True

    def test_unusable_entry_is_kept_as_invalid(self):
        cfgs = parse_rooms({"PW_ROOMS": "broken=not-a-url"})
        assert cfgs[0].id == "broken"
        assert cfgs[0].invalid_reason is not None

    def test_empty_env_means_no_rooms(self):
        assert parse_rooms({}) == []
        assert parse_rooms({"PW_ROOMS": "   "}) == []


# ── Reachable / unreachable ──────────────────────────────────────────


class TestSnapshot:
    def test_reachable_room_carries_descriptor_status_and_needs(self):
        calls: list[str] = []
        svc = RoomsService(
            transport=httpx.MockTransport(
                _handler(descriptor=_ok_descriptor, needs=_ok_needs, calls=calls)
            )
        )
        rows = run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "studio"
        assert row["base_url"] == "http://room.test"
        assert row["reachable"] is True
        assert row["status"] == "healthy"
        assert row["room"]["name"] == "Studio"
        assert [n["title"] for n in row["needs_you"]] == ["Confirm the transfer"]
        assert row["error"] is None
        assert row["checked_at"] and row["last_seen"]
        assert row["last_status"] == "healthy"
        assert row["cards"] == []  # an absent cards list is honest, not invented
        # All three read-only endpoints were read.
        # plus the room's action list (cached 60 s), shown on the row
        assert set(calls) == {
            rooms.ROOM_PATH, rooms.CARDS_PATH, rooms.NEEDS_YOU_PATH, rooms.ACTIONS_PATH,
        }

    def test_connect_error_is_unreachable_not_healthy(self):
        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        svc = RoomsService(transport=httpx.MockTransport(boom))
        row = run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert row["reachable"] is False
        assert row["room"] is None
        assert row["status"] == rooms.UNREACHABLE
        assert row["error"] == "connect error"
        assert row["last_seen"] is None  # never reached

    def test_timeout_is_named_and_never_raises(self):
        def slow(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("too slow")

        svc = RoomsService(transport=httpx.MockTransport(slow))
        row = run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert row["reachable"] is False
        assert row["status"] == rooms.UNREACHABLE
        assert row["error"] == "timeout"

    def test_malformed_json_is_unreachable_with_error(self):
        svc = RoomsService(
            transport=httpx.MockTransport(
                _handler(
                    descriptor=lambda: httpx.Response(
                        200, content=b"{not json", headers={"content-type": "application/json"}
                    )
                )
            )
        )
        row = run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert row["reachable"] is False
        assert row["room"] is None
        assert row["status"] == rooms.UNREACHABLE
        assert row["error"] == "malformed JSON"

    def test_unsupported_descriptor_contract_is_incompatible(self):
        bad = dict(DESCRIPTOR, contract="room/9")
        svc = RoomsService(
            transport=httpx.MockTransport(
                _handler(descriptor=lambda: httpx.Response(200, json=bad))
            )
        )
        row = run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert row["reachable"] is True  # it answered
        assert row["room"] is None  # but we do not understand it
        assert row["status"] == rooms.INCOMPATIBLE
        assert row["status"] != "healthy"
        assert "room/9" in row["error"]
        # An incompatible descriptor's cards/needs are never used.
        assert row["cards"] == []
        assert row["needs_you"] == []

    def test_last_seen_survives_a_later_outage(self):
        state = {"up": True}

        def handle(request: httpx.Request) -> httpx.Response:
            if state["up"]:
                return _ok_descriptor() if request.url.path == rooms.ROOM_PATH else _ok_needs()
            raise httpx.ConnectError("down")

        svc = RoomsService(transport=httpx.MockTransport(handle))
        first = run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert first["last_seen"] is not None
        svc.invalidate()
        state["up"] = False
        second = run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert second["reachable"] is False
        assert second["last_seen"] == first["last_seen"]

    def test_snapshot_is_cached_for_fifteen_seconds(self):
        calls: list[str] = []
        clock = {"t": 1000.0}
        svc = RoomsService(
            transport=httpx.MockTransport(
                _handler(descriptor=_ok_descriptor, needs=_ok_needs, calls=calls)
            ),
            clock=lambda: clock["t"],
        )
        run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))
        first_count = len(calls)
        run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))
        assert len(calls) == first_count  # served from cache
        clock["t"] += rooms.CACHE_TTL_SECONDS + 1
        run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))
        assert len(calls) > first_count  # refreshed


class TestPersistedRoomHealth:
    """Room health (last-seen / last-declared-status) outlives a restart.

    The honesty fix: an unreachable room must show its real last_seen,
    not "never reached" — "never reached" only for a room that has
    truly never answered (contract room/0 rule 12).
    """

    def _up_handler(self):
        def handle(request: httpx.Request) -> httpx.Response:
            if request.url.path == rooms.ROOM_PATH:
                return _ok_descriptor()
            if request.url.path == rooms.CARDS_PATH:
                return httpx.Response(200, json=[])
            return _ok_needs()

        return handle

    @staticmethod
    def _down_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    def test_last_seen_survives_a_restart(self, tmp_path):
        state_path = tmp_path / "rooms-state.json"
        env = {"PW_ROOMS": "studio=http://room.test"}
        first_svc = RoomsService(
            transport=httpx.MockTransport(self._up_handler()), state_path=state_path
        )
        first = run(first_svc.snapshot(env))[0]
        assert first["last_seen"] and first["last_status"] == "healthy"
        assert state_path.exists()

        # Simulated restart: a fresh service, room now down.
        second_svc = RoomsService(
            transport=httpx.MockTransport(self._down_handler), state_path=state_path
        )
        row = run(second_svc.snapshot(env))[0]
        assert row["reachable"] is False
        assert row["status"] == rooms.UNREACHABLE
        assert row["last_seen"] == first["last_seen"]  # real, not "never"
        assert row["last_status"] == "healthy"  # last status it declared
        assert row["error"] == "connect error"

    def test_never_answered_room_is_honestly_never_reached(self, tmp_path):
        state_path = tmp_path / "rooms-state.json"
        svc = RoomsService(
            transport=httpx.MockTransport(self._down_handler), state_path=state_path
        )
        row = run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert row["status"] == rooms.UNREACHABLE
        assert row["last_seen"] is None
        assert row["last_status"] is None

    def test_corrupt_state_file_never_fabricates_last_seen(self, tmp_path):
        state_path = tmp_path / "rooms-state.json"
        state_path.write_text("{not json")
        svc = RoomsService(
            transport=httpx.MockTransport(self._down_handler), state_path=state_path
        )
        row = run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert row["last_seen"] is None

    def test_last_declared_status_is_carried_for_other_statuses(self, tmp_path):
        state_path = tmp_path / "rooms-state.json"
        degraded = dict(DESCRIPTOR, status="degraded")
        up = RoomsService(
            transport=httpx.MockTransport(
                _handler(descriptor=lambda: httpx.Response(200, json=degraded))
            ),
            state_path=state_path,
        )
        first = run(up.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert first["last_status"] == "degraded"
        down = RoomsService(
            transport=httpx.MockTransport(self._down_handler), state_path=state_path
        )
        row = run(down.snapshot({"PW_ROOMS": "studio=http://room.test"}))[0]
        assert row["last_status"] == "degraded"
        assert row["last_seen"] == first["last_seen"]


class TestTokenHeader:
    def test_token_sent_only_when_configured(self):
        tokens: list[str | None] = []
        svc = RoomsService(
            transport=httpx.MockTransport(
                _handler(descriptor=_ok_descriptor, needs=_ok_needs, tokens=tokens)
            )
        )
        run(svc.snapshot({"PW_ROOMS": "studio=http://room.test"}))
        assert all(t is None for t in tokens)

        tokens.clear()
        svc.invalidate()
        run(
            svc.snapshot(
                {
                    "PW_ROOMS": "studio=http://room.test",
                    "PW_ROOM_STUDIO_TOKEN_ENV": "PW_STUDIO_TOKEN",
                    "PW_STUDIO_TOKEN": TOKEN_VALUE,
                }
            )
        )
        assert tokens and all(t == f"Bearer {TOKEN_VALUE}" for t in tokens)


# ── The route ────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    app = create_app(tmp_path, tmp_path)
    return TestClient(app)


class TestRoomsRoute:
    def test_route_requires_auth(self, client):
        assert client.get("/api/rooms").status_code == 401

    def test_route_returns_honest_rows(self, client, monkeypatch):
        import personal_world.api as api_mod
        from personal_world.rooms import RoomsService

        svc = RoomsService(
            transport=httpx.MockTransport(
                _handler(descriptor=_ok_descriptor, needs=_ok_needs)
            )
        )
        monkeypatch.setattr(api_mod, "_ROOMS", svc)
        monkeypatch.setenv("PW_ROOMS", "studio=http://room.test")
        response = client.get(
            "/api/rooms", headers={"Authorization": "Bearer instancetoken"}
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"][0]["id"] == "studio"
        assert payload["data"][0]["reachable"] is True

    def test_registry_field_is_additive_and_honest(self, client, monkeypatch):
        import personal_world.api as api_mod

        monkeypatch.setattr(
            api_mod,
            "_ROOMS",
            RoomsService(
                transport=httpx.MockTransport(
                    _handler(descriptor=_ok_descriptor, needs=_ok_needs)
                )
            ),
        )
        monkeypatch.setenv("PW_ROOMS", "studio=http://room.test")
        payload = client.get(
            "/api/rooms", headers={"Authorization": "Bearer instancetoken"}
        ).json()
        # The existing envelope is untouched…
        assert payload["ok"] is True
        assert payload["data"][0]["id"] == "studio"
        assert "resume" in payload and "summary" in payload
        # …and the registry report is a new sibling, honestly "env".
        assert payload["registry"]["source"] == "env"
        assert payload["registry"]["status"] == "not_configured"

    def test_registry_room_is_addressable_without_restart(self, client, monkeypatch):
        """A registry-only room id passes the visit route's 404 gate.

        The id is not in PW_ROOMS (unset); it is known only because the
        registry snapshot resolved it at runtime.
        """
        import personal_world.api as api_mod

        def handle(request: httpx.Request) -> httpx.Response:
            if request.url.host == "registry.test":
                return httpx.Response(
                    200,
                    json={
                        "updated_at": "2026-09-25T12:00:00Z",
                        "rooms": [
                            {
                                "id": "workshop",
                                "name": "Workshop",
                                "base_url": "http://room.test",
                                "contract": "room/0",
                                "token_env": None,
                                "insecure_tls": False,
                                "enabled": True,
                            }
                        ],
                    },
                )
            if request.url.path == rooms.ROOM_PATH:
                return _ok_descriptor()
            if request.url.path == rooms.CARDS_PATH:
                return httpx.Response(200, json=[])
            if request.url.path == rooms.NEEDS_YOU_PATH:
                return httpx.Response(200, json=[])
            return httpx.Response(404)

        monkeypatch.setattr(
            api_mod,
            "_ROOMS",
            RoomsService(transport=httpx.MockTransport(handle)),
        )
        monkeypatch.delenv("PW_ROOMS", raising=False)
        monkeypatch.setenv("PW_ROOMS_REGISTRY_URL", "https://registry.test/api/rooms/registry")
        auth = {"Authorization": "Bearer instancetoken"}

        listed = client.get("/api/rooms", headers=auth).json()
        assert [r["id"] for r in listed["data"]] == ["workshop"]
        assert listed["registry"]["source"] == "registry"

        assert client.post("/api/rooms/workshop/visit", json={}, headers=auth).status_code == 200
        assert client.post("/api/rooms/studio/visit", json={}, headers=auth).status_code == 404

    def test_registry_public_url_is_surfaced_on_rows(self, client, monkeypatch):
        """A registry entry's public_url rides the /api/rooms row; an
        invalid one leaves the entry in place with an honest null."""
        import personal_world.api as api_mod

        def handle(request: httpx.Request) -> httpx.Response:
            if request.url.host == "registry.test":
                return httpx.Response(
                    200,
                    json={
                        "updated_at": "2026-09-25T12:00:00Z",
                        "rooms": [
                            {
                                "id": "workshop",
                                "name": "Workshop",
                                "base_url": "http://room.test",
                                "public_url": "https://workshop.example",
                                "contract": "room/0",
                                "token_env": None,
                                "insecure_tls": False,
                                "enabled": True,
                            },
                            {
                                "id": "studio",
                                "name": "Studio",
                                "base_url": "http://studio.test",
                                "public_url": "https://user:pass@studio.test",
                                "contract": "room/0",
                                "token_env": None,
                                "insecure_tls": False,
                                "enabled": True,
                            },
                        ],
                    },
                )
            if request.url.path == rooms.ROOM_PATH:
                return _ok_descriptor()
            if request.url.path == rooms.CARDS_PATH:
                return httpx.Response(200, json=[])
            if request.url.path == rooms.NEEDS_YOU_PATH:
                return httpx.Response(200, json=[])
            return httpx.Response(404)

        monkeypatch.setattr(
            api_mod,
            "_ROOMS",
            RoomsService(transport=httpx.MockTransport(handle)),
        )
        monkeypatch.delenv("PW_ROOMS", raising=False)
        monkeypatch.setenv(
            "PW_ROOMS_REGISTRY_URL", "https://registry.test/api/rooms/registry"
        )
        rows = client.get(
            "/api/rooms", headers={"Authorization": "Bearer instancetoken"}
        ).json()["data"]
        by_id = {r["id"]: r for r in rows}
        assert by_id["workshop"]["public_url"] == "https://workshop.example"
        # A userinfo-bearing public URL is refused, not the room.
        assert by_id["studio"]["public_url"] is None


class TestBriefingReadsRooms:
    """The briefing reads the same one cached snapshot — no second round."""

    def test_briefing_workshop_system_comes_from_its_room(self, client, monkeypatch):
        import personal_world.api as api_mod

        needs = [
            {"id": f"n{i}", "title": f"Bench item {i}", "why": "waiting",
             "actions": [], "created_at": "2026-09-25T12:30:00Z"}
            for i in range(32)
        ]
        svc = RoomsService(
            transport=httpx.MockTransport(
                _handler(
                    descriptor=_ok_descriptor,
                    needs=lambda: httpx.Response(200, json=needs),
                )
            )
        )
        monkeypatch.setattr(api_mod, "_ROOMS", svc)
        monkeypatch.setenv("PW_ROOMS", "workshop=http://room.test")

        body = client.get(
            "/api/briefing", headers={"Authorization": "Bearer instancetoken"}
        ).json()
        assert body["ok"] is True
        agents = next(
            s for s in body["data"]["systems"] if s["id"] == "agents"
        )
        assert agents["status"] == "healthy"
        assert agents["counts"]["have_tos"] == 32
        assert body["data"]["have_tos_total"] == 32

    def test_unreachable_room_never_reports_the_system_healthy(
        self, client, monkeypatch
    ):
        import personal_world.api as api_mod

        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(
            api_mod, "_ROOMS", RoomsService(transport=httpx.MockTransport(boom))
        )
        monkeypatch.setenv("PW_ROOMS", "workshop=http://room.test")

        body = client.get(
            "/api/briefing", headers={"Authorization": "Bearer instancetoken"}
        ).json()
        agents = next(
            s for s in body["data"]["systems"] if s["id"] == "agents"
        )
        assert agents["status"] == "unavailable"
        assert agents["status"] != "healthy"

    def test_incompatible_room_never_reports_the_system_healthy(
        self, client, monkeypatch
    ):
        """An unsupported contract maps to the existing not-healthy word
        ``needs_attention`` and its needs are never counted."""
        import personal_world.api as api_mod

        bad = dict(DESCRIPTOR, contract="room/9")
        svc = RoomsService(
            transport=httpx.MockTransport(
                _handler(
                    descriptor=lambda: httpx.Response(200, json=bad),
                    needs=_ok_needs,
                )
            )
        )
        monkeypatch.setattr(api_mod, "_ROOMS", svc)
        monkeypatch.setenv("PW_ROOMS", "workshop=http://room.test")

        body = client.get(
            "/api/briefing", headers={"Authorization": "Bearer instancetoken"}
        ).json()
        agents = next(
            s for s in body["data"]["systems"] if s["id"] == "agents"
        )
        assert agents["status"] == "needs_attention"
        assert agents["status"] != "healthy"
        assert agents["counts"]["have_tos"] == 0
        assert body["data"]["have_tos_total"] == 0

def test_registry_token_env_must_name_a_room_token():
    """A registry entry can't make Worlds send PW_API_TOKEN (or any other
    secret) to a room URL: only PW_ROOM_*_TOKEN names are honoured."""
    from personal_world import rooms

    env = {"PW_API_TOKEN": "secret-api", "PW_ROOM_WORKSHOP_TOKEN": "room-tok"}
    good = {"id": "workshop", "base_url": "https://w.test", "contract": "room/0", "token_env": "PW_ROOM_WORKSHOP_TOKEN"}
    bad = {"id": "evil", "base_url": "https://evil.test", "contract": "room/0", "token_env": "PW_API_TOKEN"}
    parsed, _dropped = rooms._parse_registry_entries([good, bad], env)
    configs = {c.id: c for c in parsed}
    assert configs["workshop"].token == "room-tok"
    assert not configs["evil"].token and not configs["evil"].token_env


def test_registry_owner_token_env_must_name_a_room_owner_token():
    """Same allow-list rule, for the owner token: a registry entry can't
    redirect PW_API_TOKEN (or any other secret) here either — only
    PW_ROOM_*_OWNER_TOKEN names are honoured."""
    from personal_world import rooms

    env = {
        "PW_API_TOKEN": "secret-api",
        "PW_ROOM_WORKSHOP_TOKEN": "room-tok",
        "PW_ROOM_WORKSHOP_OWNER_TOKEN": "room-owner-tok",
    }
    good = {
        "id": "workshop", "base_url": "https://w.test", "contract": "room/0",
        "token_env": "PW_ROOM_WORKSHOP_TOKEN",
        "owner_token_env": "PW_ROOM_WORKSHOP_OWNER_TOKEN",
    }
    bad = {
        "id": "evil", "base_url": "https://evil.test", "contract": "room/0",
        "token_env": "PW_ROOM_WORKSHOP_TOKEN",
        "owner_token_env": "PW_API_TOKEN",
    }
    parsed, _dropped = rooms._parse_registry_entries([good, bad], env)
    configs = {c.id: c for c in parsed}
    assert configs["workshop"].owner_token == "room-owner-tok"
    assert not configs["evil"].owner_token and not configs["evil"].owner_token_env


def test_owner_token_env_survives_last_known_good(tmp_path):
    """The owner token env var NAME (never a value) persists through
    last-known-good, the same as the ordinary token_env."""
    from personal_world.rooms import RoomsService

    registry_path = tmp_path / "rooms-registry.json"
    svc = RoomsService(registry_state_path=registry_path)
    svc._lkg = {
        "updated_at": "2026-09-28T00:00:00Z",
        "fetched_at": "2026-09-28T00:00:00Z",
        "rooms": [
            {
                "id": "workshop", "base_url": "https://w.test",
                "contract": "room/0", "token_env": "PW_ROOM_WORKSHOP_TOKEN",
                "owner_token_env": "PW_ROOM_WORKSHOP_OWNER_TOKEN",
                "insecure_tls": False, "public_url": None,
                "forward_principal": False, "name": None,
            }
        ],
    }
    svc._persist_registry_lkg()
    stored = json.loads(registry_path.read_text())
    assert stored["rooms"][0]["owner_token_env"] == "PW_ROOM_WORKSHOP_OWNER_TOKEN"

    env = {"PW_ROOM_WORKSHOP_OWNER_TOKEN": "room-owner-tok"}
    configs, _dropped = svc._configs_from_lkg(env)
    assert configs[0].owner_token == "room-owner-tok"
