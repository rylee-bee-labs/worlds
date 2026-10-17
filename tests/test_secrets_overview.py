"""Secrets overview — the Worlds side of the read-only Secrets board.

``GET /api/secrets/overview`` finds the registry room named ``workshop``
and reads that room's read-only ``GET /api/secrets/summary`` with the
room's own token/TLS policy (3 s timeout, cached 60 s). These tests pin:

* the happy path: the station summary is returned with ``room_id`` and
  an ``open_url`` built from ``public_url`` (or ``base_url``) +
  ``links.trusted_form``;
* the room's bearer token is sent on the read and never appears in the
  response;
* a wrongly-included secret ``value`` key never survives the response;
* workshop missing from the registry, an unreachable station, a 401, a
  timeout and malformed JSON all report ``station.status: "unknown"``
  with a plain-words detail and empty lists — never raising, never
  inventing keys;
* the 60 s cache is honoured.

The transport is ``httpx.MockTransport``; no network is touched.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.rooms import RoomsService

REGISTRY_URL = "https://registry.test/api/rooms/registry"
SUMMARY_PATH = "/api/secrets/summary"

# Synthetic, short, never a real credential.
TOKEN_VALUE = "tok-abc"
TOKEN_ENV_NAME = "PW_ROOM_WORKSHOP_TOKEN"

SUMMARY = {
    "station": {"configured": True, "status": "ok", "detail": None},
    "namespaces": [
        {"name": "infra", "keys": ["tls/cert", "db/password"]},
        {"name": "apps", "keys": ["smtp/token"]},
    ],
    "key_count": 3,
    "bundle_last_change": "2026-09-25T12:00:00Z",
    "requests": [
        {
            "id": "req-1",
            "key_path": "infra/db/password",
            "reason": "rotate the database password",
            "requested_at": "2026-09-25T11:00:00Z",
            "link": "/secrets?request=req-1",
        }
    ],
    "recent_ops": [
        {
            "key_path": "infra/tls/cert",
            "state": "ok",
            "deploy_state": "deployed",
            "actor": "operator",
            "created_at": "2026-09-25T10:00:00Z",
        }
    ],
    "links": {"trusted_form": "/secrets"},
}


def run(coro):
    return asyncio.run(coro)


def _registry(rooms):
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"updated_at": "2026-09-25T12:00:00Z", "rooms": rooms}
        )

    return handle


def _workshop_entry(*, public_url=None, token_env=TOKEN_ENV_NAME):
    return {
        "id": "workshop",
        "name": "Workshop",
        "base_url": "http://room.test",
        "contract": "room/0",
        "token_env": token_env,
        "insecure_tls": False,
        "enabled": True,
        "public_url": public_url,
    }


def _station(summary=None, *, status=200, body=None, calls=None, tokens=None):
    """A station handler for ``/api/secrets/summary``."""

    def handle(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        if tokens is not None:
            tokens.append(request.headers.get("authorization"))
        if body is not None:
            return httpx.Response(status, content=body)
        return httpx.Response(status, json=summary if summary is not None else SUMMARY)

    return handle


def _transport(*, registry, station):
    """Route ``registry.test`` to the registry, everything else to the
    station. ``None`` rests that leg down."""

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.test":
            if registry is None:
                raise httpx.ConnectError("registry down")
            return registry(request)
        if station is None:
            raise httpx.ConnectTimeout("station timed out")
        return station(request)

    return httpx.MockTransport(handle)


def _assert_no_value_key(node):
    """No ``value`` key anywhere — a station summary may never leak one."""
    if isinstance(node, dict):
        assert "value" not in node, node
        for child in node.values():
            _assert_no_value_key(child)
    elif isinstance(node, list):
        for child in node:
            _assert_no_value_key(child)


class TestOverviewHappyPath:
    def test_reads_the_workshop_summary_and_opens_through_public_url(self):
        tokens: list = []
        svc = RoomsService(
            transport=_transport(
                registry=_registry(
                    [_workshop_entry(public_url="https://workshop.example")]
                ),
                station=_station(tokens=tokens),
            )
        )
        data = run(
            svc.secrets_overview(
                {"PW_ROOMS_REGISTRY_URL": REGISTRY_URL, TOKEN_ENV_NAME: TOKEN_VALUE}
            )
        )
        assert data["room_id"] == "workshop"
        assert data["station"] == {"configured": True, "status": "ok", "detail": None}
        assert data["key_count"] == 3
        assert [ns["name"] for ns in data["namespaces"]] == ["infra", "apps"]
        assert data["namespaces"][0]["keys"] == ["tls/cert", "db/password"]
        assert data["bundle_last_change"] == "2026-09-25T12:00:00Z"
        assert data["requests"][0]["link"] == "/secrets?request=req-1"
        assert data["recent_ops"][0]["deploy_state"] == "deployed"
        # public_url is preferred over base_url for the browser-open link.
        assert data["open_url"] == "https://workshop.example/secrets"
        # The room token is sent on the read, and never in the response.
        assert tokens == [f"Bearer {TOKEN_VALUE}"]
        blob = json.dumps(data)
        assert TOKEN_VALUE not in blob
        assert TOKEN_ENV_NAME not in blob

    def test_open_url_falls_back_to_base_url_without_public_url(self):
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_workshop_entry(public_url=None)]),
                station=_station(),
            )
        )
        data = run(svc.secrets_overview({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        assert data["open_url"] == "http://room.test/secrets"

    def test_a_wrongly_included_value_key_never_survives(self):
        leaky = dict(SUMMARY)
        leaky["namespaces"] = [
            {
                "name": "infra",
                "keys": ["tls/cert"],
                "value": "should-never-appear",
            }
        ]
        leaky["requests"] = [
            {"id": "r", "key_path": "infra/tls/cert", "value": "should-never-appear"}
        ]
        leaky["value"] = "should-never-appear"
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_workshop_entry()]),
                station=_station(leaky),
            )
        )
        data = run(svc.secrets_overview({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        _assert_no_value_key(data)
        assert "should-never-appear" not in json.dumps(data)


class TestOverviewUnknown:
    def _assert_unknown(self, data):
        assert data["station"]["status"] == "unknown"
        assert isinstance(data["station"]["detail"], str)
        assert data["station"]["detail"]  # words, not an empty string
        assert data["namespaces"] == []
        assert data["requests"] == []
        assert data["recent_ops"] == []
        assert data["key_count"] == 0
        assert data["bundle_last_change"] is None
        assert data["room_id"] == "workshop"

    def test_workshop_missing_from_the_registry(self):
        other = dict(_workshop_entry(), id="studio", name="Studio")
        svc = RoomsService(
            transport=_transport(
                registry=_registry([other]), station=_station()
            )
        )
        data = run(svc.secrets_overview({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        self._assert_unknown(data)
        assert "workshop" in data["station"]["detail"]
        assert "registry" in data["station"]["detail"]

    def test_unreachable_station(self):
        svc = RoomsService(
            transport=_transport(registry=_registry([_workshop_entry()]), station=None)
        )
        data = run(svc.secrets_overview({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        self._assert_unknown(data)
        assert data["station"]["detail"] == "timeout"

    def test_401_is_named_in_words(self):
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_workshop_entry()]),
                station=_station(status=401, summary={}),
            )
        )
        data = run(svc.secrets_overview({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        self._assert_unknown(data)
        assert "unauthorized" in data["station"]["detail"].lower()

    def test_malformed_json_is_named_in_words(self):
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_workshop_entry()]),
                station=_station(body=b"{not json"),
            )
        )
        data = run(svc.secrets_overview({"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}))
        self._assert_unknown(data)
        assert "malformed" in data["station"]["detail"].lower()


class TestOverviewCache:
    def test_cache_is_honoured_for_60s(self):
        clock = {"t": 1000.0}
        calls: list = []
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_workshop_entry()]),
                station=_station(calls=calls),
            ),
            clock=lambda: clock["t"],
        )
        env = {"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}
        first = run(svc.secrets_overview(env))
        second = run(svc.secrets_overview(env))
        assert first == second
        assert calls == [SUMMARY_PATH]  # one read, cached

        # Past the 60 s TTL: the station is read again.
        clock["t"] += 61
        run(svc.secrets_overview(env))
        assert calls == [SUMMARY_PATH, SUMMARY_PATH]

    def test_invalidate_drops_the_overview_cache(self):
        calls: list = []
        svc = RoomsService(
            transport=_transport(
                registry=_registry([_workshop_entry()]),
                station=_station(calls=calls),
            )
        )
        env = {"PW_ROOMS_REGISTRY_URL": REGISTRY_URL}
        run(svc.secrets_overview(env))
        svc.invalidate()
        run(svc.secrets_overview(env))
        assert calls == [SUMMARY_PATH, SUMMARY_PATH]


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


AUTH = {"Authorization": "Bearer instancetoken"}


class TestOverviewRoute:
    def test_route_requires_auth(self, client):
        assert client.get("/api/secrets/overview").status_code == 401

    def test_route_returns_the_overview(self, client, monkeypatch):
        import personal_world.api as api_mod

        monkeypatch.setattr(
            api_mod,
            "_ROOMS",
            RoomsService(
                transport=_transport(
                    registry=_registry(
                        [_workshop_entry(public_url="https://workshop.example")]
                    ),
                    station=_station(),
                )
            ),
        )
        monkeypatch.setenv("PW_ROOMS_REGISTRY_URL", REGISTRY_URL)
        response = client.get("/api/secrets/overview", headers=AUTH)
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"]["station"]["status"] == "ok"
        assert payload["data"]["open_url"] == "https://workshop.example/secrets"
        assert "value" not in response.text
        assert TOKEN_VALUE not in response.text

def test_route_is_admin_only_in_multi_mode(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    c = TestClient(create_app(tmp_path, tmp_path))
    r = c.post(
        "/api/identity/users",
        json={"user_id": "second", "display_name": "Second"},
        headers={"Authorization": "Bearer instancetoken", "X-PW-StepUp": "1"},
    )
    assert r.status_code == 200, r.text
    second = {"Authorization": f"Bearer {r.json()['data']['token']}"}
    assert c.get("/api/secrets/overview", headers=second).status_code == 403
    owner = c.get("/api/secrets/overview", headers={"Authorization": "Bearer instancetoken"})
    assert owner.status_code == 200
