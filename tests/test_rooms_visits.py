"""Rooms visit state — Worlds-owned, private, per principal.

``GET /api/rooms`` carries the caller's own visit fields and a
``resume``/``summary`` sibling of ``data``; two POST endpoints record a
visit and mark a need seen. This is Worlds-owned state: it is never sent
to a room, it is per-principal (two people cannot see each other's
visits), and it rides the existing per-principal JSON seam.

Pinned here:

* a never-visited room is ``last_visited_at: null`` with
  ``changed_since_visit: 0`` — never "everything changed";
* ``changed_since_visit`` counts only cards observed after the visit;
* ``summary`` counts unseen needs, changed cards, ``when_ready`` cards,
  unknown-room needs, and unreachable rooms, each per the honest rules;
* POST visit: 404 for an unconfigured room, 422 for a non-same-origin
  link, idempotent in effect;
* POST need-seen: idempotent, capped;
* two principals do not see each other's visits/seen-needs.

No network: ``httpx.MockTransport`` feeds the room.
"""

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import rooms, rooms_visits  # noqa: E402
from personal_world.rooms import RoomsService  # noqa: E402

TOKEN = "instancetoken"  # pw-safety: synthetic

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
        "link": "/tasks/2",
        "created_at": "2026-09-25T12:30:00Z",
    }
]

#: Observed far in the future → newer than any visit recorded "now".
CARD_FUTURE = {
    "id": "card-future",
    "title": "Rent due soon",
    "body": "Next withdrawal is scheduled.",
    "link": "/ledger/rent",
    "lane": "personal",
    "tone": "update",
    "freshness": {"observed_at": "2099-01-01T00:00:00Z", "stale_after_s": 3600},
}
#: Observed long ago → never counts as changed.
CARD_PAST = {
    "id": "card-past",
    "title": "Old news",
    "lane": "personal",
    "tone": "good_news",
    "freshness": {"observed_at": "2000-01-01T00:00:00Z", "stale_after_s": 3600},
}
CARD_WAIT = {
    "id": "card-wait",
    "title": "When you're ready",
    "lane": "personal",
    "tone": "when_ready",
    "freshness": {"observed_at": "2099-01-02T00:00:00Z", "stale_after_s": 3600},
}
CARDS = [CARD_FUTURE, CARD_PAST, CARD_WAIT]


def _handler(*, descriptor=None, cards=None, needs=None):
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == rooms.ROOM_PATH:
            return descriptor() if descriptor else httpx.Response(200, json=DESCRIPTOR)
        if request.url.path == rooms.CARDS_PATH:
            return cards() if cards else httpx.Response(200, json=CARDS)
        if request.url.path == rooms.NEEDS_YOU_PATH:
            return needs() if needs else httpx.Response(200, json=NEEDS)
        return httpx.Response(404, json={"detail": "unknown"})

    return handle


def _down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down")


def _install(monkeypatch, handler=None, state_path=None):
    import personal_world.api as api_mod

    monkeypatch.setenv("PW_ROOMS", "studio=http://room.test")
    monkeypatch.setattr(
        api_mod,
        "_ROOMS",
        RoomsService(
            transport=httpx.MockTransport(handler or _handler()),
            state_path=state_path,
        ),
    )


def _mk_app(tmp_path, monkeypatch, mode="single"):
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    return create_app(tmp_path, tmp_path)


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    return TestClient(_mk_app(tmp_path, monkeypatch, "single"))


def _auth(tok=TOKEN):
    return {"Authorization": f"Bearer {tok}"}


def _rows(payload):
    return {row["id"]: row for row in payload["data"]}


# ── unit: the private-state helpers ───────────────────────────────────


class TestSameOriginLink:
    def test_accepts_plain_same_origin_paths(self):
        for good in ("/tasks/2", "/ledger/rent", "/"):
            assert rooms_visits.valid_same_origin_link(good), good

    def test_rejects_schemes_protocol_relative_and_junk(self):
        for bad in (
            "//evil.com",
            "https://evil.test/x",
            "http://evil.test",
            "javascript:alert(1)",
            "tasks/2",
            "",
            None,
            7,
            "/bad\\path",
            "/line\nbreak",
        ):
            assert not rooms_visits.valid_same_origin_link(bad), bad


class TestChangedSinceVisit:
    def test_never_visited_counts_nothing(self):
        assert rooms_visits.changed_since_visit(CARDS, None) == 0

    def test_counts_only_cards_observed_after_the_visit(self):
        # visit "now"; only the 2099 cards are newer.
        assert rooms_visits.changed_since_visit(CARDS, "2026-09-25T00:00:00Z") == 2
        # a visit after every card → nothing changed
        assert rooms_visits.changed_since_visit(CARDS, "2100-01-01T00:00:00Z") == 0

    def test_unparseable_timestamps_stay_unknown(self):
        weird = [{"freshness": {"observed_at": "not-a-time"}}]
        assert rooms_visits.changed_since_visit(weird, "2026-09-25T00:00:00Z") == 0
        assert rooms_visits.changed_since_visit(CARDS, "not-a-time") == 0


class TestNeedsSeenCap:
    def test_dedupes_and_caps_the_stored_list(self):
        state = rooms_visits.empty_state()
        for i in range(rooms_visits.NEEDS_SEEN_CAP + 1):
            rooms_visits.mark_need_seen(state, "studio", f"need-{i}")
        seen = state["rooms"]["studio"]["needs_seen"]
        assert len(seen) == rooms_visits.NEEDS_SEEN_CAP
        assert seen[0] == "need-1"  # oldest dropped
        # idempotent: re-marking an existing id changes nothing
        rooms_visits.mark_need_seen(state, "studio", seen[-1])
        assert len(seen) == rooms_visits.NEEDS_SEEN_CAP


# ── API: visit fields, resume, summary ────────────────────────────────


class TestRoomsViewVisitState:
    def test_never_visited_is_null_and_zero(self, client, monkeypatch):
        _install(monkeypatch)
        payload = client.get("/api/rooms", headers=_auth()).json()
        row = _rows(payload)["studio"]
        assert row["last_visited_at"] is None
        assert row["needs_seen"] == []
        assert row["changed_since_visit"] == 0
        assert payload["resume"] is None
        # the room itself is fine; only the private visit state is empty
        assert row["reachable"] is True

    def test_visit_records_time_resume_and_changed_count(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.post(
            "/api/rooms/studio/visit",
            json={"link": "/studio/today", "title": "Studio"},
            headers=_auth(),
        )
        assert r.status_code == 200, r.text
        resumed = r.json()["data"]["resume"]
        assert resumed["room_id"] == "studio"
        assert resumed["link"] == "/studio/today"
        assert resumed["title"] == "Studio"

        payload = client.get("/api/rooms", headers=_auth()).json()
        row = _rows(payload)["studio"]
        assert row["last_visited_at"] == r.json()["data"]["last_visited_at"]
        # 2 cards observed after the visit (2000 card is older).
        assert row["changed_since_visit"] == 2
        assert payload["resume"]["link"] == "/studio/today"

    def test_summary_counts_roles_honestly(self, client, monkeypatch):
        _install(monkeypatch)
        before = client.get("/api/rooms", headers=_auth()).json()
        assert before["summary"] == {
            "needs_you": 1,  # one unseen need
            "changed": 0,  # never visited → nothing changed
            "can_wait": 1,  # exactly one when_ready card
            "unknown": 0,
            "unreachable": 0,
        }
        client.post("/api/rooms/studio/visit", json={}, headers=_auth())
        after = client.get("/api/rooms", headers=_auth()).json()
        assert after["summary"] == {
            "needs_you": 1,
            "changed": 2,  # the two future-observed cards
            "can_wait": 1,
            "unknown": 0,
            "unreachable": 0,
        }

    def test_seen_need_leaves_the_needs_you_count(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.post(
            "/api/rooms/studio/needs/need-1/seen", headers=_auth()
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["needs_seen"] == ["need-1"]
        payload = client.get("/api/rooms", headers=_auth()).json()
        assert payload["summary"]["needs_you"] == 0
        assert _rows(payload)["studio"]["needs_seen"] == ["need-1"]

    def test_incompatible_room_needs_are_not_counted(self, client, monkeypatch):
        # An unsupported contract is "incompatible": its needs/cards are
        # never used for the summary (never current, never "unknown needs").
        bad = dict(DESCRIPTOR, contract="room/9")
        _install(
            monkeypatch,
            handler=_handler(descriptor=lambda: httpx.Response(200, json=bad)),
        )
        payload = client.get("/api/rooms", headers=_auth()).json()
        row = _rows(payload)["studio"]
        assert row["status"] == "incompatible"
        assert row["status"] != "healthy"
        assert row["needs_you"] == []
        assert payload["summary"]["needs_you"] == 0
        assert payload["summary"]["unknown"] == 0

    def test_unreachable_room_is_counted_and_never_health(self, client, monkeypatch):
        _install(monkeypatch, handler=_down)
        payload = client.get("/api/rooms", headers=_auth()).json()
        row = _rows(payload)["studio"]
        assert row["reachable"] is False
        assert row["status"] == "unreachable"  # always a word
        assert row["last_status"] is None  # truly never answered
        assert payload["summary"]["unreachable"] == 1
        assert payload["summary"]["needs_you"] == 0


class TestVisitRouteValidation:
    def test_route_requires_auth(self, client):
        assert client.post("/api/rooms/studio/visit", json={}).status_code == 401

    def test_unconfigured_room_is_404(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.post("/api/rooms/nope/visit", json={}, headers=_auth())
        assert r.status_code == 404

    @pytest.mark.parametrize("bad", ["//evil.com", "https://evil.test/x", "tasks/2"])
    def test_bad_link_is_422_and_nothing_stored(self, client, monkeypatch, bad):
        _install(monkeypatch)
        r = client.post(
            "/api/rooms/studio/visit", json={"link": bad}, headers=_auth()
        )
        assert r.status_code == 422
        payload = client.get("/api/rooms", headers=_auth()).json()
        assert payload["resume"] is None

    def test_good_link_is_stored(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.post(
            "/api/rooms/studio/visit", json={"link": "/tasks/2"}, headers=_auth()
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["resume"]["link"] == "/tasks/2"

    def test_visit_is_idempotent_in_effect(self, client, monkeypatch):
        _install(monkeypatch)
        for _ in range(3):
            r = client.post(
                "/api/rooms/studio/visit", json={"link": "/x"}, headers=_auth()
            )
            assert r.status_code == 200
        payload = client.get("/api/rooms", headers=_auth()).json()
        assert len(_rows(payload)) == 1  # one room, one visit record

    def test_need_seen_is_idempotent(self, client, monkeypatch):
        _install(monkeypatch)
        for _ in range(2):
            client.post("/api/rooms/studio/needs/need-1/seen", headers=_auth())
        payload = client.get("/api/rooms", headers=_auth()).json()
        assert _rows(payload)["studio"]["needs_seen"] == ["need-1"]


# ── per-principal isolation ───────────────────────────────────────────


def test_visit_state_isolated_between_principals(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    app = _mk_app(tmp_path, monkeypatch, "multi")
    client = TestClient(app)
    _install(monkeypatch)

    # provision a second person with their own bearer token
    r = client.post(
        "/api/identity/users",
        json={"user_id": "beta", "display_name": "Beta"},
        headers={**_auth(), "X-PW-StepUp": "1"},
    )
    assert r.status_code == 200, r.text
    beta = r.json()["data"]["token"]

    # alpha visits studio and marks its need seen
    assert (
        client.post(
            "/api/rooms/studio/visit",
            json={"link": "/studio/alpha", "title": "Studio"},
            headers=_auth(),
        ).status_code
        == 200
    )
    client.post("/api/rooms/studio/needs/need-1/seen", headers=_auth())

    alpha = client.get("/api/rooms", headers=_auth()).json()
    beta_payload = client.get("/api/rooms", headers=_auth(beta)).json()

    alpha_row = _rows(alpha)["studio"]
    beta_row = _rows(beta_payload)["studio"]
    assert alpha_row["last_visited_at"] is not None
    assert alpha_row["needs_seen"] == ["need-1"]
    assert alpha["resume"]["link"] == "/studio/alpha"

    assert beta_row["last_visited_at"] is None
    assert beta_row["needs_seen"] == []
    assert beta_payload["resume"] is None
    assert beta_payload["summary"]["needs_you"] == 1  # beta has seen nothing

    # stored on the caller's own tree, never the other person's
    assert (tmp_path / "users" / "primary" / "rooms-visits.json").exists()
    assert not (tmp_path / "users" / "beta" / "rooms-visits.json").exists()

def test_visit_time_keeps_sub_second_precision():
    """Regression: a whole-second visit stamp made a card observed later in
    the same second count as 'changed since your visit'."""
    from personal_world import rooms_visits

    state = rooms_visits.empty_state()
    rooms_visits.record_visit(state, "studio", at="2026-09-25T21:32:39.900000+00:00")
    row = {"id": "studio", "reachable": True, "status": "healthy", "needs_you": [],
           "cards": [{"id": "c1", "freshness": {"observed_at": "2026-09-25T21:32:39.555278+00:00"}}]}
    assert rooms_visits.decorate_row(row, state)["changed_since_visit"] == 0
