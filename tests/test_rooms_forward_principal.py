"""Rooms per-person forwarding — telling a room who is asking.

Multi-user Candy, step 4. A registry room can opt in to
``forward_principal: true``; when it also has its own bearer token,
Worlds sends ``X-Worlds-Principal: <principal id>`` on every request to
it, **in addition to** the room's token, so the room can answer for that
person. These tests pin:

* a forwarding room with a token gets the header (right id) alongside
  ``Authorization`` on all three read endpoints;
* a forwarding opt-in with NO token sends no header and behaves as
  non-forwarding (an unauthenticated identity claim is meaningless);
* a room that did not opt in never gets the header;
* two principals see their own cards and neither sees the other's (the
  full multi-mode stack: two provisioned users, ``GET /api/rooms``);
* the per-principal cache honours the 15 s TTL and the 64-principal cap;
* ``forward_principal`` survives last-known-good;
* invalid principal ids are never sent;
* the human's session token / ``PW_API_TOKEN`` is never sent to a room.

The transport is ``httpx.MockTransport`` — no network is touched.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import rooms
from personal_world.identity import Principal
from personal_world.rooms import RoomsService

REGISTRY_URL = "https://registry.test/api/rooms/registry"
TOKEN_ENV_NAME = "PW_ROOM_WORKSHOP_TOKEN"
# Synthetic, short, never a real credential.
TOKEN_VALUE = "tok-abc"

DESCRIPTOR = {
    "contract": "room/0",
    "id": "workshop",
    "name": "Workshop",
    "icon": "wrench",
    "version": "1.0.0",
    "commit": "a1b2c3d",
    "status": "healthy",
    "updated_at": "2026-09-25T13:05:48Z",
}


def run(coro):
    return asyncio.run(coro)


def _entry(*, forward_principal=True, token_env=TOKEN_ENV_NAME, enabled=True):
    return {
        "id": "workshop",
        "name": "Workshop",
        "base_url": "http://room.test",
        "contract": "room/0",
        "token_env": token_env,
        "insecure_tls": False,
        "enabled": enabled,
        "public_url": None,
        "forward_principal": forward_principal,
    }


def _transport(*, registry=None, room=None):
    """Route ``registry.test`` to the registry handler, else to the room."""

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.test":
            if registry is None:
                raise httpx.ConnectError("registry down")
            return registry(request)
        if room is None:
            raise httpx.ConnectError("room down")
        return room(request)

    return httpx.MockTransport(handle)


def _registry(rooms_entries, *, forward_principal=True):
    payload = {
        "updated_at": "2026-09-25T12:00:00Z",
        "rooms": [
            _entry(forward_principal=forward_principal) for _ in rooms_entries
        ],
    }

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return handle


def _room(cards_for=None, needs_for=None, seen=None, paths=None):
    """A room whose cards/needs may depend on the forwarded principal."""

    def handle(request: httpx.Request) -> httpx.Response:
        if paths is not None:
            paths.append(request.url.path)
        if seen is not None:
            seen.append(request.headers.get(rooms.PRINCIPAL_HEADER))
        pid = request.headers.get(rooms.PRINCIPAL_HEADER)
        if request.url.path == rooms.ROOM_PATH:
            return httpx.Response(200, json=DESCRIPTOR)
        if request.url.path == rooms.CARDS_PATH:
            cards = cards_for(pid) if cards_for is not None else []
            return httpx.Response(200, json=cards)
        if request.url.path == rooms.NEEDS_YOU_PATH:
            needs = needs_for(pid) if needs_for is not None else []
            return httpx.Response(200, json=needs)
        return httpx.Response(404, json={"detail": "unknown"})

    return handle


def _env():
    return {
        "PW_ROOMS_REGISTRY_URL": REGISTRY_URL,
        TOKEN_ENV_NAME: TOKEN_VALUE,
    }


# ── The header ───────────────────────────────────────────────────────


class TestForwardingHeader:
    def test_header_sent_with_principal_id_alongside_bearer_token(self):
        calls: list[tuple[str, str | None, str | None]] = []

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(
                (
                    request.url.path,
                    request.headers.get(rooms.PRINCIPAL_HEADER),
                    request.headers.get("authorization"),
                )
            )
            return _room()(request)

        svc = RoomsService(
            transport=_transport(registry=_registry([1]), room=handle)
        )
        rows = run(svc.snapshot_for_principal(Principal(id="alice"), _env()))
        # The forwarded read — one per read endpoint — carried the id…
        forwarded = [c for c in calls if c[1] == "alice"]
        assert {c[0] for c in forwarded} == {
            rooms.ROOM_PATH,
            rooms.CARDS_PATH,
            rooms.NEEDS_YOU_PATH,
        }
        # …and every request (the estate-wide probe included) carried the
        # room's own token, never instead of the header.
        assert all(c[2] == f"Bearer {TOKEN_VALUE}" for c in calls)
        assert all(c[1] in (None, "alice") for c in calls)
        assert len(rows) == 1 and rows[0]["reachable"] is True

    def test_no_token_means_no_header_and_non_forwarding(self):
        seen: list[str | None] = []
        svc = RoomsService(
            transport=_transport(
                registry=_registry([1]), room=_room(seen=seen)
            )
        )
        # An entry that opted in but names no token: the header is never
        # sent (no authentication → no identity claim) and the room is
        # not fetched per principal at all.
        env = {"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}
        rows = run(svc.snapshot_for_principal(Principal(id="alice"), env))
        assert seen and all(s is None for s in seen)
        assert svc._principal_cache == {}
        assert len(rows) == 1

    def test_non_forwarding_room_never_gets_the_header(self):
        seen: list[str | None] = []
        svc = RoomsService(
            transport=_transport(
                registry=_registry([1], forward_principal=False),
                room=_room(seen=seen),
            )
        )
        run(svc.snapshot_for_principal(Principal(id="alice"), _env()))
        assert seen and all(s is None for s in seen)
        assert svc._principal_cache == {}

    def test_invalid_principal_ids_are_never_sent(self):
        # The same safe-id rule identity.principal_scoped_path uses.
        bad_ids = [
            "",
            "bad id",
            "-leading",
            "with/slash",
            "a" * 65,
            "tab\there",
        ]
        for bad in bad_ids:
            seen: list[str | None] = []
            svc = RoomsService(
                transport=_transport(
                    registry=_registry([1]), room=_room(seen=seen)
                )
            )
            run(svc.snapshot_for_principal(Principal(id=bad), _env()))
            assert seen and all(s is None for s in seen), bad
            assert svc._principal_cache == {}, bad

    def test_session_token_is_never_sent_to_a_room(self):
        seen_headers: list[dict] = []

        def handle(request: httpx.Request) -> httpx.Response:
            seen_headers.append(dict(request.headers))
            return _room()(request)

        svc = RoomsService(
            transport=_transport(registry=_registry([1]), room=handle)
        )
        env = dict(_env(), PW_API_TOKEN="instancetoken")
        run(svc.snapshot_for_principal(Principal(id="alice"), env))
        blob = json.dumps(seen_headers)
        assert "instancetoken" not in blob
        assert all(
            h.get("authorization") == f"Bearer {TOKEN_VALUE}"
            for h in seen_headers
        )


# ── Per-principal cache ──────────────────────────────────────────────


class TestPerPrincipalCache:
    def test_forwarded_rows_honour_ttl(self):
        hits: list[str | None] = []
        clock = {"t": 1000.0}
        svc = RoomsService(
            transport=_transport(
                registry=_registry([1]), room=_room(seen=hits)
            ),
            clock=lambda: clock["t"],
        )
        env = _env()
        alice = Principal(id="alice")
        run(svc.snapshot_for_principal(alice, env))
        first = sum(1 for h in hits if h == "alice")
        assert first > 0

        # Inside the 15 s TTL: the shared snapshot and the forwarded row
        # both come from cache — no new alice request.
        run(svc.snapshot_for_principal(alice, env))
        assert sum(1 for h in hits if h == "alice") == first

        clock["t"] += rooms.CACHE_TTL_SECONDS + 1
        run(svc.snapshot_for_principal(alice, env))
        assert sum(1 for h in hits if h == "alice") > first

    def test_forwarded_rows_cap_at_64_principals_evicting_oldest(self):
        svc = RoomsService(
            transport=_transport(registry=_registry([1]), room=_room())
        )
        env = _env()
        for i in range(rooms.MAX_FORWARD_PRINCIPALS + 1):
            run(svc.snapshot_for_principal(Principal(id=f"u{i}"), env))
        assert len(svc._principal_cache) == rooms.MAX_FORWARD_PRINCIPALS
        assert ("workshop", "u0") not in svc._principal_cache  # oldest evicted
        assert ("workshop", "u64") in svc._principal_cache

    def test_forward_principal_survives_last_known_good(self, tmp_path):
        state = tmp_path / "rooms-registry.json"
        env = _env()
        up = RoomsService(
            transport=_transport(registry=_registry([1]), room=_room()),
            registry_state_path=state,
        )
        run(up.snapshot(env))
        assert state.exists()
        stored = json.loads(state.read_text())
        assert stored["rooms"][0]["forward_principal"] is True

        down = RoomsService(
            transport=_transport(registry=None, room=_room()),
            registry_state_path=state,
        )
        config = run(down.resolved_config("workshop", env))
        assert config is not None
        assert config.forward_principal is True


# ── Two principals, the whole stack ──────────────────────────────────


def test_two_principals_get_their_own_cards_and_nothing_of_the_other(
    tmp_path, monkeypatch
):
    """Multi identity mode: primary and a provisioned second user each get
    their own cards from the same forwarding room, and neither sees the
    other's. The room's health stays estate-wide."""
    from fastapi.testclient import TestClient

    import personal_world.api as api_mod
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_ROOMS_REGISTRY_URL", REGISTRY_URL)
    monkeypatch.setenv(TOKEN_ENV_NAME, TOKEN_VALUE)
    monkeypatch.delenv("PW_ROOMS", raising=False)

    cards = {
        "primary": [{"id": "a1", "title": "Alpha card", "tone": "update"}],
        "beta": [{"id": "b1", "title": "Beta card", "tone": "update"}],
    }
    seen: list[tuple[str, str | None, str | None]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.test":
            return _registry([1])(request)
        pid = request.headers.get(rooms.PRINCIPAL_HEADER)
        seen.append(
            (
                request.url.path,
                pid,
                request.headers.get("authorization"),
            )
        )
        return _room(cards_for=lambda p: cards.get(p, []))(request)

    monkeypatch.setattr(
        api_mod, "_ROOMS", RoomsService(transport=httpx.MockTransport(handle))
    )
    client = TestClient(create_app(tmp_path, tmp_path))

    admin = {"Authorization": "Bearer instancetoken", "X-PW-StepUp": "1"}
    provisioned = client.post(
        "/api/identity/users",
        json={"user_id": "beta", "display_name": "Beta"},
        headers=admin,
    )
    assert provisioned.status_code == 200, provisioned.text
    beta_token = provisioned.json()["data"]["token"]

    def rows_for(token):
        response = client.get(
            "/api/rooms", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, response.text
        return {r["id"]: r for r in response.json()["data"]}

    alpha_rows = rows_for("instancetoken")
    beta_rows = rows_for(beta_token)

    alpha_titles = [c["title"] for c in alpha_rows["workshop"]["cards"]]
    beta_titles = [c["title"] for c in beta_rows["workshop"]["cards"]]
    assert alpha_titles == ["Alpha card"]
    assert beta_titles == ["Beta card"]
    assert "Beta card" not in alpha_titles  # neither sees the other's
    assert "Alpha card" not in beta_titles
    # Health is estate-wide and identical for both.
    for rows in (alpha_rows, beta_rows):
        assert rows["workshop"]["reachable"] is True
        assert rows["workshop"]["status"] == "healthy"
    # Each caller's forwarded read carried their own id, alongside the
    # room's token (never the session/instance token).
    assert ("/room/cards", "primary", f"Bearer {TOKEN_VALUE}") in seen
    assert ("/room/cards", "beta", f"Bearer {TOKEN_VALUE}") in seen
    assert all(auth != "Bearer instancetoken" for _, _, auth in seen)
