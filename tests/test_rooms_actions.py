"""Rooms actions — passing a room/0 action through and returning its receipt.

Design board Spec-Approve / owner decision 2026-09-26 ("approving from
Worlds, owner-only"). ``POST /api/rooms/{room_id}/actions/{action_id}``
names one action on one configured room; Worlds reads the room's own
``GET /room/actions`` list (cached 60 s per room) to enforce owner-only
writes, requires an ``Idempotency-Key``, forwards the call to the room
with the room's token and the caller's ``X-Worlds-Principal``, and
returns the room's own receipt. These tests pin:

* a room's receipt passes through and is allow-listed to exactly
  ``{action_id, ok, summary, changed, at}``;
* the outbound call carries ``Idempotency-Key`` and ``X-Worlds-Principal``
  alongside the room's token, and never ``PW_API_TOKEN``;
* a write action needs the ``approve`` permission (403 without it),
  while a ``writes: false`` action passes through for anyone;
* an unknown action is a 404 receipt;
* a missing/malformed ``Idempotency-Key`` is a 400 receipt;
* malformed ids and incompatible/disabled rooms are 404 receipts;
* an unreachable/timing-out/non-receipt room yields an ``ok: false``
  "nothing changed" receipt with HTTP 200 — never a 500;
* a body over 16 KB is a 413 receipt;
* a successful action drops the cached snapshot (and the caller's
  forwarded row);
* two users in multi mode: the owner can act, a second user cannot write
  but can call a read-only action.

The transport is ``httpx.MockTransport`` — no network is touched.
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import rooms  # noqa: E402
from personal_world.identity import Principal  # noqa: E402
from personal_world.rooms import RoomsService  # noqa: E402

REGISTRY_URL = "https://registry.test/api/rooms/registry"
TOKEN_ENV_NAME = "PW_ROOM_WORKSHOP_TOKEN"
OWNER_TOKEN_ENV_NAME = "PW_ROOM_WORKSHOP_OWNER_TOKEN"
# Synthetic, short, never a real credential.
TOKEN_VALUE = "tok-abc"
OWNER_TOKEN_VALUE = "owner-tok-xyz"

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

#: The room's own action list. ``approve`` writes, ``refresh`` does not,
#: and ``mystery`` omits ``writes`` (must fail closed as a write).
ACTIONS = [
    {"id": "approve", "label": "Approve", "writes": True},
    {"id": "refresh", "label": "Refresh", "writes": False},
    {"id": "mystery", "label": "Mystery"},
]


def run(coro):
    return asyncio.run(coro)


def _env(*, token=True, owner_token=False):
    env = {
        "PW_ROOMS": "workshop=http://room.test",
        "PW_ROOM_WORKSHOP_TOKEN_ENV": TOKEN_ENV_NAME,
    }
    if token:
        env[TOKEN_ENV_NAME] = TOKEN_VALUE
    if owner_token:
        env["PW_ROOM_WORKSHOP_OWNER_TOKEN_ENV"] = OWNER_TOKEN_ENV_NAME
        env[OWNER_TOKEN_ENV_NAME] = OWNER_TOKEN_VALUE
    return env


def _receipt_response(status=200, **fields):
    payload = {
        "action_id": "refresh",
        "ok": True,
        "summary": "Refreshed.",
        "changed": ["card-1"],
        "at": "2026-09-26T08:00:00Z",
        **fields,
    }
    return httpx.Response(status, json=payload)


def _transport(*, actions=ACTIONS, action=None, seen=None):
    """Route room.test: its read endpoints, its action list, its action.

    ``action`` is the handler for ``POST /room/actions/{id}``; ``None``
    means the room is down (connect error) for the action call only.
    """

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == rooms.ACTIONS_PATH:
            if actions is None:
                raise httpx.ConnectError("actions list down")
            return httpx.Response(200, json=actions)
        if path.startswith(rooms.ACTIONS_PATH + "/"):
            if seen is not None:
                seen.append(request)
            if action is None:
                raise httpx.ConnectError("room down")
            return action(request)
        if path == rooms.ROOM_PATH:
            return httpx.Response(200, json=DESCRIPTOR)
        if path == rooms.CARDS_PATH:
            return httpx.Response(200, json=[])
        if path == rooms.NEEDS_YOU_PATH:
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"detail": "unknown"})

    return httpx.MockTransport(handle)


def _registry_transport(*, entry_overrides=None, action=None, seen=None):
    """Registry room ``workshop`` (room.test), plus the room handlers."""
    entry = {
        "id": "workshop",
        "name": "Workshop",
        "base_url": "http://room.test",
        "contract": "room/0",
        "token_env": TOKEN_ENV_NAME,
        "insecure_tls": False,
        "enabled": True,
    }
    entry.update(entry_overrides or {})
    room = _transport(action=action, seen=seen)

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "registry.test":
            return httpx.Response(
                200,
                json={
                    "updated_at": "2026-09-25T12:00:00Z",
                    "rooms": [entry],
                },
            )
        return room.handler(request)

    return httpx.MockTransport(handle)


def _act(svc, **kwargs):
    params = {
        "room_id": "workshop",
        "action_id": "refresh",
        "principal": Principal(id="primary"),
        "idempotency_key": "key-1",
        "body": b"{}",
        "env": _env(),
    }
    params.update(kwargs)
    return run(
        svc.perform_action(
            params["room_id"],
            params["action_id"],
            params["principal"],
            params["idempotency_key"],
            params["body"],
            params["env"],
        )
    )


# ── The receipt ──────────────────────────────────────────────────────


class TestReceipt:
    def test_passes_through_and_allow_lists_the_rooms_receipt(self):
        def action(request: httpx.Request) -> httpx.Response:
            payload = {
                "action_id": "refresh",
                "ok": True,
                "summary": "Refreshed.",
                "changed": ["card-1"],
                "at": "2026-09-26T08:00:00Z",
                # A hostile/extra key must never ride through.
                "token": "leak-me",
            }
            return httpx.Response(200, json=payload)

        svc = RoomsService(transport=_transport(action=action))
        status, receipt = _act(svc)
        assert status == 200
        assert receipt == {
            "action_id": "refresh",
            "ok": True,
            "summary": "Refreshed.",
            "changed": ["card-1"],
            "at": "2026-09-26T08:00:00Z",
        }
        assert "token" not in receipt

    def test_any_room_status_with_a_receipt_body_passes_through_as_200(self):
        # The room refused the action (409) but said so in a receipt: the
        # receipt's own ok/ summary is what the caller reads.
        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response(
                409, ok=False, summary="The bench is busy; nothing changed."
            )

        svc = RoomsService(transport=_transport(action=action))
        status, receipt = _act(svc)
        assert status == 200
        assert receipt["ok"] is False
        assert receipt["summary"] == "The bench is busy; nothing changed."

    def test_room_receipt_not_an_object_falls_back_honestly(self):
        def action(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=["not", "a", "receipt"])

        svc = RoomsService(transport=_transport(action=action))
        status, receipt = _act(svc)
        assert status == 200
        assert receipt["ok"] is False
        assert receipt["summary"] == (
            "Couldn't reach workshop, so nothing changed."
        )
        assert receipt["changed"] == []
        assert receipt["action_id"] == "refresh"


# ── Forwarding ───────────────────────────────────────────────────────


class TestForwarding:
    def test_forwards_idempotency_key_and_principal_with_room_token(self):
        seen: list[httpx.Request] = []

        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response()

        svc = RoomsService(transport=_transport(action=action, seen=seen))
        env = dict(_env(), PW_API_TOKEN="instancetoken")
        status, _ = _act(
            svc,
            principal=Principal(id="alice"),
            idempotency_key="abc.123:xyz-9",
            body=b'{"reason": "because"}',
            env=env,
        )
        assert status == 200
        assert len(seen) == 1
        request = seen[0]
        assert request.method == "POST"
        assert request.url.path == "/room/actions/refresh"
        assert request.headers["idempotency-key"] == "abc.123:xyz-9"
        assert request.headers[rooms.PRINCIPAL_HEADER] == "alice"
        assert request.headers["authorization"] == f"Bearer {TOKEN_VALUE}"
        assert request.content == b'{"reason": "because"}'
        # The human's credential never goes to a room.
        assert "instancetoken" not in json.dumps(dict(request.headers))

    def test_principal_header_rides_even_without_forward_opt_in(self):
        # Unlike reads, an action is always someone's: the header is sent
        # whenever the room has a token, no registry opt-in required.
        seen: list[httpx.Request] = []

        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response()

        svc = RoomsService(transport=_transport(action=action, seen=seen))
        _act(svc, principal=Principal(id="alice"), env=_env())
        assert seen[0].headers[rooms.PRINCIPAL_HEADER] == "alice"

    def test_no_token_means_no_authorization_and_no_principal(self):
        seen: list[httpx.Request] = []

        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response()

        svc = RoomsService(transport=_transport(action=action, seen=seen))
        _act(svc, principal=Principal(id="alice"), env=_env(token=False))
        assert "authorization" not in seen[0].headers
        assert rooms.PRINCIPAL_HEADER not in seen[0].headers


# ── Owner-only writes ────────────────────────────────────────────────


class TestOwnerOnly:
    def test_non_admin_cannot_call_a_write(self):
        def action(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            return _receipt_response()

        svc = RoomsService(transport=_transport(action=action))
        status, receipt = _act(
            svc, action_id="approve", principal=Principal(id="beta")
        )
        assert status == 403
        assert receipt["ok"] is False
        assert receipt["summary"] == "Only the owner can do that here."

    def test_missing_writes_field_fails_closed_as_a_write(self):
        svc = RoomsService(transport=_transport(action=_receipt_response))
        status, receipt = _act(
            svc, action_id="mystery", principal=Principal(id="beta")
        )
        assert status == 403
        assert receipt["summary"] == "Only the owner can do that here."

    def test_non_admin_may_call_a_read_only_action(self):
        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response(status=200, ok=True, summary="Refreshed.")

        svc = RoomsService(transport=_transport(action=action))
        status, receipt = _act(
            svc, action_id="refresh", principal=Principal(id="beta")
        )
        assert status == 200
        assert receipt["ok"] is True

    def test_admin_scope_grants_the_write(self):
        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response(status=200, summary="Approved.")

        svc = RoomsService(transport=_transport(action=action))
        status, _ = _act(
            svc,
            action_id="approve",
            principal=Principal(id="carol", scopes=("admin",)),
        )
        assert status == 200

    @pytest.mark.parametrize("role", ["member", "supervised", "guest"])
    def test_role_without_approve_is_refused_a_write(self, role):
        """The `approve` permission, not a name: these roles have no
        approve, so a write is refused whatever they are called."""
        svc = RoomsService(transport=_transport(action=_receipt_response))
        status, receipt = _act(
            svc, action_id="approve", principal=Principal(id="beta", role=role)
        )
        assert status == 403
        assert receipt["summary"] == "Only the owner can do that here."

    @pytest.mark.parametrize("role", ["owner", "admin"])
    def test_role_with_approve_may_write(self, role):
        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response(status=200, summary="Approved.")

        svc = RoomsService(transport=_transport(action=action))
        status, _ = _act(
            svc, action_id="approve", principal=Principal(id="carol", role=role)
        )
        assert status == 200

    def test_agent_never_writes_a_room_action(self):
        """An agent holds no `approve`, even under an owner's tree."""
        svc = RoomsService(transport=_transport(action=_receipt_response))
        status, _ = _act(
            svc,
            action_id="approve",
            principal=Principal(
                id="bot",
                kind="agent",
                owner_id="primary",
                scopes=("write", "read"),
                role="owner",
            ),
        )
        assert status == 403


# ── Owner token (X-Worlds-Owner-Token) ──────────────────────────────


class TestOwnerToken:
    """A room may require a second, stronger secret on a write action —
    ``PW_ROOM_<ID>_OWNER_TOKEN_ENV`` — because ``X-Worlds-Principal`` is
    client-supplied and not cryptographically bound to the caller
    (hive-works, 2026-09-28). Generic and keyed only by the action's own
    ``writes`` flag, not by room or action id."""

    def test_owner_token_rides_a_write_action_when_configured(self):
        seen: list[httpx.Request] = []

        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response(status=200, summary="Approved.")

        svc = RoomsService(transport=_transport(action=action, seen=seen))
        status, _ = _act(
            svc,
            action_id="approve",
            principal=Principal(id="carol", role="owner"),
            env=_env(owner_token=True),
        )
        assert status == 200
        assert seen[0].headers[rooms.OWNER_HEADER] == OWNER_TOKEN_VALUE
        # The room's own bearer token and the principal still ride too —
        # the owner token is additive, never a replacement.
        assert seen[0].headers["authorization"] == f"Bearer {TOKEN_VALUE}"
        assert seen[0].headers[rooms.PRINCIPAL_HEADER] == "carol"

    def test_no_owner_header_when_the_room_has_none_configured(self):
        """Most rooms today configure no owner token: unaffected."""
        seen: list[httpx.Request] = []

        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response(status=200, ok=True, summary="Refreshed.")

        svc = RoomsService(transport=_transport(action=action, seen=seen))
        status, _ = _act(
            svc,
            action_id="refresh",
            principal=Principal(id="beta"),
            env=_env(owner_token=False),
        )
        assert status == 200
        assert rooms.OWNER_HEADER not in seen[0].headers

    def test_no_owner_header_on_a_read_only_action_even_if_configured(self):
        """Keyed by the action's own ``writes`` flag: a room that
        configured an owner token still doesn't get it on a non-write."""
        seen: list[httpx.Request] = []

        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response(status=200, ok=True, summary="Refreshed.")

        svc = RoomsService(transport=_transport(action=action, seen=seen))
        status, _ = _act(
            svc,
            action_id="refresh",
            principal=Principal(id="beta"),
            env=_env(owner_token=True),
        )
        assert status == 200
        assert rooms.OWNER_HEADER not in seen[0].headers

    def test_no_owner_header_without_the_rooms_own_bearer_token(self):
        """No room token at all means no Authorization and no owner
        header either — the owner token is additive to, not a
        substitute for, the room's own bearer token."""
        seen: list[httpx.Request] = []

        def action(request: httpx.Request) -> httpx.Response:
            return _receipt_response(status=200, summary="Approved.")

        svc = RoomsService(transport=_transport(action=action, seen=seen))
        env = _env(token=False, owner_token=True)
        status, _ = _act(
            svc,
            action_id="approve",
            principal=Principal(id="carol", role="owner"),
            env=env,
        )
        assert "authorization" not in seen[0].headers
        assert rooms.OWNER_HEADER not in seen[0].headers


# ── Local refusals ───────────────────────────────────────────────────


class TestLocalRefusals:
    def test_unknown_action_is_a_404_receipt(self):
        svc = RoomsService(transport=_transport(action=_receipt_response))
        status, receipt = _act(svc, action_id="nope")
        assert status == 404
        assert receipt["ok"] is False
        assert receipt["summary"] == "That room doesn't offer that."

    def test_unreadable_action_list_fails_closed(self):
        svc = RoomsService(transport=_transport(actions=None, action=_receipt_response))
        status, receipt = _act(svc)
        assert status == 404
        assert receipt["summary"] == "That room doesn't offer that."
        assert svc._actions_cache  # the failed read is cached, no hammering

    def test_missing_idempotency_key_is_a_400_receipt(self):
        svc = RoomsService(transport=_transport(action=_receipt_response))
        status, receipt = _act(svc, idempotency_key=None)
        assert status == 400
        assert receipt["ok"] is False

    def test_malformed_idempotency_key_is_a_400_receipt(self):
        for bad in ("", "has space", "x" * 129, "nope!"):
            svc = RoomsService(transport=_transport(action=_receipt_response))
            status, _ = _act(svc, idempotency_key=bad)
            assert status == 400, bad

    def test_bad_room_and_action_ids_are_404_receipts(self):
        svc = RoomsService(transport=_transport(action=_receipt_response))
        assert _act(svc, room_id="Bad_ID")[0] == 404
        assert _act(svc, room_id="")[0] == 404
        assert _act(svc, action_id="Bad")[0] == 404
        assert _act(svc, action_id="a" * 65)[0] == 404

    def test_body_over_16kb_is_a_413_receipt(self):
        svc = RoomsService(transport=_transport(action=_receipt_response))
        body = b'{"x":"' + b"a" * (16 * 1024) + b'"}'
        status, receipt = _act(svc, body=body)
        assert status == 413
        assert receipt["ok"] is False

    def test_non_object_body_is_a_400_receipt(self):
        svc = RoomsService(transport=_transport(action=_receipt_response))
        status, receipt = _act(svc, body=b'["not", "an", "object"]')
        assert status == 400
        assert receipt["ok"] is False


# ── Room configuration gates ─────────────────────────────────────────


class TestConfigGates:
    def test_incompatible_room_is_a_404_receipt(self):
        svc = RoomsService(
            transport=_registry_transport(
                entry_overrides={"contract": "room/9"}, action=_receipt_response
            )
        )
        env = {"PW_ROOMS_REGISTRY_URL": REGISTRY_URL, TOKEN_ENV_NAME: TOKEN_VALUE}
        status, receipt = _act(svc, env=env)
        assert status == 404
        assert receipt["ok"] is False

    def test_disabled_room_is_a_404_receipt(self):
        svc = RoomsService(
            transport=_registry_transport(
                entry_overrides={"enabled": False}, action=_receipt_response
            )
        )
        env = {"PW_ROOMS_REGISTRY_URL": REGISTRY_URL, TOKEN_ENV_NAME: TOKEN_VALUE}
        status, _ = _act(svc, env=env)
        assert status == 404

    def test_unconfigured_room_is_a_404_receipt(self):
        svc = RoomsService(transport=_transport(action=_receipt_response))
        status, _ = _act(svc, room_id="studio")
        assert status == 404


# ── Room failures never raise ────────────────────────────────────────


class TestRoomFailures:
    def test_unreachable_room_is_an_ok_false_receipt_with_200(self):
        svc = RoomsService(transport=_transport(action=None))
        status, receipt = _act(svc)
        assert status == 200
        assert receipt["ok"] is False
        assert receipt["summary"] == (
            "Couldn't reach workshop, so nothing changed."
        )
        assert receipt["changed"] == []
        assert receipt["at"]

    def test_timeout_is_an_ok_false_receipt_with_200(self):
        def action(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out")

        svc = RoomsService(transport=_transport(action=action))
        status, receipt = _act(svc)
        assert status == 200
        assert receipt["ok"] is False

    def test_non_receipt_body_is_an_ok_false_receipt_with_200(self):
        def action(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        svc = RoomsService(transport=_transport(action=action))
        status, receipt = _act(svc)
        assert status == 200
        assert receipt["ok"] is False

    def test_failure_summary_uses_the_rooms_name_when_it_has_one(self):
        svc = RoomsService(
            transport=_registry_transport(action=None)
        )
        env = {"PW_ROOMS_REGISTRY_URL": REGISTRY_URL, TOKEN_ENV_NAME: TOKEN_VALUE}
        status, receipt = _act(svc, env=env)
        assert status == 200
        assert receipt["summary"] == (
            "Couldn't reach Workshop, so nothing changed."
        )


# ── Cache invalidation ───────────────────────────────────────────────


class TestCacheInvalidation:
    def test_success_drops_the_snapshot_and_this_callers_forwarded_row(self):
        calls: list[str] = []

        def handle(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            if request.url.host == "registry.test":
                return _registry_transport().handler(request)
            return _transport(action=_receipt_response).handler(request)

        svc = RoomsService(
            transport=httpx.MockTransport(handle),
            clock=lambda: 1000.0,
        )
        env = dict(
            _env(),
            PW_ROOMS_REGISTRY_URL=REGISTRY_URL,
            PW_ROOM_WORKSHOP_TOKEN=TOKEN_VALUE,
        )
        # Populate the shared snapshot AND the caller's forwarded row.
        run(svc.snapshot_for_principal(Principal(id="primary"), env))
        assert svc._cache is not None
        # Seed a forwarded row directly for the caller (the registry entry
        # here is not a forwarding room, so nothing else would cache one).
        svc._principal_cache[("workshop", "primary")] = (1000.0, {"id": "workshop"})

        status, receipt = _act(
            svc, action_id="refresh", principal=Principal(id="primary"), env=env
        )
        assert status == 200 and receipt["ok"] is True
        assert svc._cache is None  # next /api/rooms re-reads the room
        assert ("workshop", "primary") not in svc._principal_cache

    def test_failed_action_leaves_the_cache_in_place(self):
        svc = RoomsService(
            transport=_transport(action=None), clock=lambda: 1000.0
        )
        run(svc.snapshot(_env()))
        assert svc._cache is not None
        status, receipt = _act(svc, action_id="refresh")
        assert status == 200 and receipt["ok"] is False
        assert svc._cache is not None


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


class TestActionRoute:
    def test_requires_auth(self, client):
        response = client.post(
            "/api/rooms/workshop/actions/refresh",
            headers={"Idempotency-Key": "k-1"},
            json={"x": 1},
        )
        assert response.status_code == 401

    def test_room_answered_receipt_comes_back_enveloped(self, client, monkeypatch):
        import personal_world.api as api_mod

        monkeypatch.setattr(
            api_mod,
            "_ROOMS",
            RoomsService(transport=_transport(action=_receipt_response)),
        )
        monkeypatch.setenv("PW_ROOMS", "workshop=http://room.test")
        response = client.post(
            "/api/rooms/workshop/actions/refresh",
            headers={
                "Authorization": "Bearer instancetoken",
                "Idempotency-Key": "k-1",
            },
            json={"reason": "please"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"]["ok"] is True
        assert payload["data"]["summary"] == "Refreshed."

    def test_local_refusal_carries_an_error_envelope(self, client, monkeypatch):
        import personal_world.api as api_mod

        monkeypatch.setattr(
            api_mod,
            "_ROOMS",
            RoomsService(transport=_transport(action=_receipt_response)),
        )
        monkeypatch.setenv("PW_ROOMS", "workshop=http://room.test")
        response = client.post(
            "/api/rooms/workshop/actions/refresh",
            headers={"Authorization": "Bearer instancetoken"},
            json={},
        )
        assert response.status_code == 400
        payload = response.json()
        assert payload["ok"] is False
        assert payload["data"]["ok"] is False


# ── Two users, the whole stack ───────────────────────────────────────


def test_two_users_owner_can_write_second_user_cannot(tmp_path, monkeypatch):
    """Multi identity mode: primary (the owner) can call a write action;
    a provisioned second user gets 403 for the write but 200 for the
    read-only action. Every outbound call carries the caller's principal
    and the room's token, never the instance token."""
    from fastapi.testclient import TestClient

    import personal_world.api as api_mod
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PW_ROOMS_REGISTRY_URL", REGISTRY_URL)
    monkeypatch.setenv(TOKEN_ENV_NAME, TOKEN_VALUE)
    monkeypatch.delenv("PW_ROOMS", raising=False)

    seen: list[tuple[str, str | None, str | None]] = []

    def action(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.url.path,
                request.headers.get(rooms.PRINCIPAL_HEADER),
                request.headers.get("authorization"),
            )
        )
        # Echo which action was called so the two calls are distinguishable.
        called = request.url.path.rsplit("/", 1)[-1]
        return _receipt_response(action_id=called, summary=f"{called} done")

    monkeypatch.setattr(
        api_mod,
        "_ROOMS",
        RoomsService(transport=_registry_transport(action=action, seen=None)),
    )
    client = TestClient(create_app(tmp_path, tmp_path))

    admin_headers = {"Authorization": "Bearer instancetoken", "X-PW-StepUp": "1"}
    provisioned = client.post(
        "/api/identity/users",
        json={"user_id": "beta", "display_name": "Beta"},
        headers=admin_headers,
    )
    assert provisioned.status_code == 200, provisioned.text
    beta_token = provisioned.json()["data"]["token"]

    def act(token, action_id):
        return client.post(
            f"/api/rooms/workshop/actions/{action_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "k-1",
            },
            json={},
        )

    owner_write = act("instancetoken", "approve")
    assert owner_write.status_code == 200, owner_write.text
    assert owner_write.json()["data"]["ok"] is True

    second_write = act(beta_token, "approve")
    assert second_write.status_code == 403, second_write.text
    assert (
        second_write.json()["data"]["summary"]
        == "Only the owner can do that here."
    )

    second_read = act(beta_token, "refresh")
    assert second_read.status_code == 200, second_read.text
    assert second_read.json()["data"]["ok"] is True

    # Every outbound action carried the caller's own principal id and the
    # room's token — never the instance/session token.
    paths = [(p, pid, auth) for p, pid, auth in seen]
    assert seen and all(auth == f"Bearer {TOKEN_VALUE}" for _, _, auth in paths)
    assert {pid for _, pid, _ in paths} == {"primary", "beta"}
    assert all("instancetoken" not in (auth or "") for _, _, auth in paths)

# ── Actions on each rooms row (design ask, 2026-09-26) ──────────────


class TestActionsOnRows:
    def test_row_lists_the_rooms_actions_with_title_and_writes(self):
        svc = RoomsService(transport=_transport())
        rows = run(svc.snapshot(_env()))
        assert rows[0]["actions"] == [
            {"id": "approve", "title": "Approve", "writes": True},
            {"id": "refresh", "title": "Refresh", "writes": False},
            {"id": "mystery", "title": "Mystery", "writes": None},
        ]

    def test_unreadable_action_list_gives_an_empty_list(self):
        svc = RoomsService(transport=_transport(actions=None))
        rows = run(svc.snapshot(_env()))
        assert rows[0]["actions"] == []


# ── Action forms (the Hive Works Riff button, 2026-09-27) ───────────

RIFF_ACTIONS = [
    {"id": "start-riff", "label": "Riff", "writes": True,
     "input_schema": {"type": "object", "required": ["seed"], "properties": {
         "seed": {"type": "string", "maxLength": 500, "title": "What's on your mind?"},
         "bees": {"type": "array", "maxItems": 4, "items": {"type": "string", "enum": ["buzz", "pip"]}},
         "door": {"type": "string", "enum": ["angles", "soft"], "enumNames": ["New angles", "Soft"]}}}},
    {"id": "riff-reply", "label": "Answer the riff", "writes": True,
     "input_schema": {"type": "object", "properties": {"need": {"type": "string"}, "text": {"type": "string"}}}},
    {"id": "odd", "label": "Odd", "writes": True,
     "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}}}},
    {"id": "evil", "label": "Evil", "writes": True,
     "input_schema": {"type": "object", "properties": {"x": {"type": "string", "enum": ["<script>" * 10]}}}},
]


class TestActionForms:
    def _rows(self):
        svc = RoomsService(transport=_transport(actions=RIFF_ACTIONS))
        return {a["id"]: a for a in run(svc.snapshot(_env()))[0]["actions"]}

    def test_a_schema_becomes_a_small_checked_form(self):
        riff = self._rows()["start-riff"]
        assert riff["fields"] == [
            {"name": "seed", "kind": "text", "label": "What's on your mind?", "required": True, "max_length": 500},
            {"name": "bees", "kind": "choices", "label": "Bees", "required": False, "max": 2,
             "options": [{"value": "buzz", "label": "buzz"}, {"value": "pip", "label": "pip"}]},
            {"name": "door", "kind": "choice", "label": "Door", "required": False,
             "options": [{"value": "angles", "label": "New angles"}, {"value": "soft", "label": "Soft"}]},
        ]
        assert "need_bound" not in riff

    def test_actions_that_answer_a_need_are_marked_and_get_no_form(self):
        reply = self._rows()["riff-reply"]
        assert reply["need_bound"] is True and "fields" not in reply

    def test_a_schema_the_ui_cant_draw_gives_a_plain_button(self):
        rows = self._rows()
        assert "fields" not in rows["odd"] and "fields" not in rows["evil"]
