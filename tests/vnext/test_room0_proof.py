"""Synthetic, read-only, no-network proof that Project Home can stand as the contract's room/0.

Reads with ``tests/vnext/test_connect_proof.py`` (docs/vnext/proof/c-proof.md): same fixture style, same
naming, one suite. Scope came from the c-room0 card, 2026-10-15, and the owner decision it carries
(2026-10-14 23:30Z Rylee, "After the freeze"; Sol #147, 2026-10-13).

The contract (``docs/vnext/connect-contract.md``) is a MOCKUP, so this proves room/0 against the pieces
that DO exist - ``room0.py``, ``config_store.py``, ``confinement.py``, ``dispatcher.py`` - and pins the
places the contract is ahead of the code as strict ``xfail`` in the sibling file (asserted here, never
relaxed). The three states the card names (zero-provider, stale/UNKNOWN, revoked connection) each get a
test, and a Project Home-governed room answer is shown to fail closed. The zero-provider state is also
proven at the surface a person actually reads - ``GET /api/boards/home``, wired the way production wires
it (production.py:91) - where the empty screen must still render; the explanation that surface owes the
person is pinned here as a strict ``xfail`` of its own, because no such words exist in the code today
(the UI never even reads the payload's ``first_run`` flag).

Everything is synthetic and read-only: the room is a fixture, ``base_url`` is the shipped
``*.lan.example`` placeholder (a reserved name that never resolves), the principal is the recipe's
``your-person-id`` placeholder, and no credential value, real URL, socket or write path is ever reached.
Where a browser is needed (keyboard, 390px) this file records NOT RUN in c-room0.md rather than guessing.
"""
import ast
import json
import pathlib

import pytest

from personal_world.worlds import confinement
from personal_world.worlds.cards import CardService, home_board_defs
from personal_world.worlds.config_store import ConfigStore
from personal_world.worlds.confinement import ConfinementError, RawResponse
from personal_world.worlds.models import Card, Provider
from personal_world.worlds.room0 import Room0Client, RoomService, room_card_id, status_card_id
from personal_world.worlds.runner import Runner

NOW = 1_900_000_000.0
# The recipe config/recipes/project-home/provider.yaml ships these two placeholders; both are synthetic.
PROVIDER_ID = "project-home"
BASE_URL = "https://project-home.lan.example"     # a reserved *.example name, never a live service
PRINCIPAL = "your-person-id"                      # the recipe's placeholder principal
_STAGE_C = pathlib.Path(__file__).with_name("test_connect_proof.py")


# ------------------------------------------------------------------ fixtures (same shape as test_connect_proof.py)


class Clock:
    t = NOW

    def __call__(self):
        return self.t


class RoomFixture:
    """The synthetic room. Records every call; answers per path from ``answers``.

    A path with no answer is a connection failure, so a test that forgets a route sees an honest error
    rather than a live call. ``effect`` is recorded on every call so read-only can be asserted after.
    """

    def __init__(self):
        self.calls = []
        self.answers = {}

    def __call__(self, provider, request, *, effect):
        self.calls.append({"method": request.method, "path": request.path, "effect": effect})
        reply = self.answers.get(request.path)
        if reply is None:
            return ConfinementError("connection", f"synthetic room has no answer for {request.path}", pre_send=True)
        return reply


class _NoDial:
    """Replace every function that could put bytes on a socket; if the room reaches the live seam, fail loudly.

    Room0Client is always handed the fixture sender, so the live confinement seam is never on the path;
    this guard makes that a proof instead of a promise (the same idea as ``_Dials`` in the Stage C file).
    """

    def __enter__(self):
        self._saved = (confinement._exchange, confinement._session_send, confinement._system_resolver)
        confinement._exchange = confinement._session_send = confinement._system_resolver = _boom
        return self

    def __exit__(self, *exc):
        confinement._exchange, confinement._session_send, confinement._system_resolver = self._saved
        return False


def _boom(*_a, **_k):
    pytest.fail("the room proof reached the live confinement seam; nothing may dial Project Home")


def iso(epoch: float) -> str:
    import datetime as dt
    return dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def raw(body, *, status: int = 200) -> RawResponse:
    return RawResponse(status_code=status, headers={"content-type": "application/json"},
                       body=json.dumps(body).encode(), duration_ms=3)


def good_card(room_id: str = "finds", **kw) -> dict:
    doc = {"id": room_id, "title": "New finds", "body": "New finds: 3", "link": "/finds", "tone": "good_news",
           "freshness": {"observed_at": iso(NOW - 5), "stale_after_s": 3600}}
    doc.update(kw)
    return doc


def ack_action_doc() -> dict:
    return {"id": "ack-build", "label": "Acknowledge the build plan", "writes": True, "default_autonomy": "ask_first"}


def room_doc(status: str = "healthy") -> dict:
    return {"contract": "room/0", "id": "ph", "name": "Project Home", "icon": "home", "version": "1",
            "commit": "synthetic", "status": status, "updated_at": iso(NOW)}


def healthy_room(*, status: str = "healthy", cards=(), needs=(), actions=()) -> dict:
    """The four reads ``room0._fetch`` makes, all answered: /room, /room/cards, /room/needs-you, /room/actions."""
    return {"/room": raw(room_doc(status)),
            "/room/cards": raw(list(cards)),
            "/room/needs-you": raw(list(needs)),
            "/room/actions": raw(list(actions))}


def save_room(store: ConfigStore) -> Provider:
    provider = Provider(id=PROVIDER_ID, name="Project Home", kind="room0",
                        base_url=BASE_URL, public_url=BASE_URL, principal_id=PRINCIPAL)
    store.save("provider", provider)
    return provider


@pytest.fixture
def room_world(tmp_path):
    """A ConfigStore, the synthetic room sender, a clock, and the room/0 read surface over them."""
    store = ConfigStore(tmp_path / "cfg")
    fx = RoomFixture()
    clock = Clock()
    client = Room0Client(store, fx, clock=clock, ttl_s=0)      # ttl 0 so each read is a real read
    service = RoomService(store, client, clock=clock)
    cards = CardService(store, Runner(store, fx, clock=clock), clock=clock)
    return store, fx, clock, client, service, cards


# --------------------------------------------------------------------------- state 1: zero-provider


def _home_board_client(room_world, tmp_path):
    """The surface a person reads: ``GET /api/boards/home``, wired the way production wires room items
    into it (production.py:91 passes ``home_extra=lambda: rooms.home_items()``).

    The route (server.py:164-175) is the payload the React UI's Home screen reads. Here ``home_extra``
    is the room service's ``home_items`` over the same (empty) config dir and the fixture is the send
    seam, so rendering the surface can dial nothing. Without fastapi these tests are NOT RUN, exactly
    like the ``test_c1_room0_*`` tests.
    """
    _store, fx, _clock, _client, service, _cards = room_world
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from personal_world.worlds.server import build_app
    app = build_app(tmp_path / "cfg", principal_dependency=lambda: "owner", send_override=fx,
                    home_extra=lambda: service.home_items())
    return TestClient(app, base_url="http://127.0.0.1"), fx


def test_room0_zero_provider_home_board_still_renders(room_world, tmp_path):
    """Zero providers: the surface the UI reads still renders - 200 with the same keys, never a 404."""
    c, fx = _home_board_client(room_world, tmp_path)
    r = c.get("/api/boards/home")
    assert r.status_code == 200                                   # first run is a state, not an error (server.py:173-174)
    body = r.json()
    assert {"id", "title", "items"} <= set(body)                  # the same keys a populated board answers with
    assert body["items"] == []                                    # nothing to draw, not a fabricated card
    assert body["first_run"] is True                              # the empty state is named, not hidden
    assert fx.calls == []                                         # rendering the empty surface sent nothing


@pytest.mark.xfail(strict=True,
                   reason="no empty-state explanation exists: the payload carries only the bare boolean "
                          "first_run (server.py:174) and no words at all, and the UI never reads the flag "
                          "(ui/src/fd/types.ts drops it) - nothing tells the person why the screen is empty; "
                          "contract C6.1's guided start is unbuilt (personal-world#357)")
def test_room0_zero_provider_home_board_says_why_it_is_empty(room_world, tmp_path):
    """The empty screen must explain itself to the person: words in the payload, or a field the UI renders.

    docs/rebuild/CONTRACTS.md:161 promises a guided start shown from ``first_run`` ("one 'Connect your
    first service' card, plus Memory"); neither the payload nor the React UI implements any of it, so
    this pins the gap. It must flip loudly (strict xfail -> XPASS -> failure) when words are added.
    """
    c, _fx = _home_board_client(room_world, tmp_path)
    r = c.get("/api/boards/home")
    assert r.status_code == 200                                   # an error body's detail string is not an explanation
    body = r.json()
    # Everything in the payload a person could read, minus the board's own id/title: today only the bare
    # boolean first_run is left, and a boolean says nothing.
    words = [v for v in body.values() if isinstance(v, str) and v.strip() and v not in (body.get("id"), body.get("title"))]
    ui_home = pathlib.Path(__file__).resolve().parents[2] / "ui" / "src" / "fd"
    ui = "".join((ui_home / name).read_text(encoding="utf-8")
                 for name in ("types.ts", "Home.tsx") if (ui_home / name).exists())
    assert words or "first_run" in ui, "nothing explains the empty Home to the person who opens it"


def test_room0_zero_provider_is_empty_and_honest(room_world):
    """No provider configured at all: the room surface is empty and says so, invents nothing, dials nothing."""
    store, fx, clock, client, service, cards = room_world
    assert service.providers() == []
    assert service.rooms() == []                                  # never an invented "connected"
    assert service.home_items() == []                             # nothing to draw, not a fabricated card
    assert service.needs() == []
    assert service.card(status_card_id(PROVIDER_ID)) is None
    assert client.snapshot(PROVIDER_ID) is None
    assert home_board_defs(store) is None
    assert cards.build(status_card_id(PROVIDER_ID)) is None
    assert fx.calls == []                                         # no provider: nothing was sent


def test_room0_a_card_for_an_absent_source_reads_not_configured(room_world):
    """The one honest word for "there is nothing here": not_configured, with values unknown - never 0."""
    store, fx, clock, client, service, cards = room_world
    ghost = Card(id="ghost-check", title="Ghost", request="ghost.health",
                 meaning={"concept": "ghost", "short": "Is the ghost fine?"},
                 fields=[{"path": "$.n", "label": "N"}])
    env = cards.build_for(ghost)
    assert env["source_state"] == "not_configured" and env["freshness"] == "stale"
    assert env["values"]["n"] == {"text": "unknown"}              # missing is unknown, never 0
    assert fx.calls == []


# ------------------------------------------------------------------- state 2: stale and UNKNOWN


def test_room0_a_stale_card_is_never_current(room_world):
    """Rule 3: a card past its own stale_after_s is stale, never current (room0.py:433-434)."""
    store, fx, clock, client, service, cards = room_world
    save_room(store)
    fx.answers = healthy_room(cards=[good_card(freshness={"observed_at": iso(NOW - 3600), "stale_after_s": 60})])
    env = service.card(room_card_id(PROVIDER_ID, "finds"))
    assert env["freshness"] == "stale" and env["freshness"] != "current"
    assert env["values"]["body"]["text"] == "New finds: 3"        # the fact is still readable...
    assert env["source_state"] == "healthy"                       # ...its lapsed freshness is what is flagged


def test_room0_last_good_after_a_failure_is_stale_not_live(room_world):
    """Rule 12: an unreachable room answers with last-known content, labelled stale, never as current."""
    store, fx, clock, client, service, cards = room_world
    save_room(store)
    fx.answers = healthy_room(cards=[good_card()])
    first = client.snapshot(PROVIDER_ID)
    assert first.error_class is None and first.stale is False and first.last_good_at is not None

    fx.answers = {}                                               # the room goes away
    second = client.snapshot(PROVIDER_ID)
    assert second.error_class == "connection" and second.stale is True
    assert second.cards and second.last_good_at == first.last_good_at   # last-good content, not nothing

    env = service.card(room_card_id(PROVIDER_ID, "finds"))
    assert env["freshness"] == "stale" and env["source_state"] == "unavailable"
    assert env["evidence"]["error_class"] == "connection"         # the failure is named, not hidden


def test_room0_unknown_is_unknown_never_healthy_or_zero(room_world):
    """A fact nobody can resolve reads unknown/degraded, never healthy and never a fabricated 0."""
    store, fx, clock, client, service, cards = room_world
    save_room(store)

    # The room's own status word is not one room0 recognises: carried as unknown, never mapped to healthy.
    fx.answers = healthy_room(status="weird")
    status_env = service.card(status_card_id(PROVIDER_ID))
    assert status_env["source_state"] == "unknown"
    assert status_env["values"]["status"]["text"] == "unknown"

    # A card whose title and freshness cannot be read honestly: degraded, every value unknown, no raw/0.
    fx.answers = healthy_room(cards=[{"id": "broken", "body": "no title here"}])
    broken = service.card(room_card_id(PROVIDER_ID, "broken"))
    assert broken["source_state"] == "degraded" and broken["freshness"] == "current"
    assert broken["values"]["body"] == {"text": "unknown"}        # unknown, and no "raw" key at all

    # An unrecognised tone is shown as the neutral 'update', never invented as good news (room0.py:155-158).
    from personal_world.worlds.room0 import parse_card
    assert parse_card(good_card(tone="triumphant")).tone == "update"


# ------------------------------------------------------------------ state 3: revoked connection


def test_room0_a_revoked_credential_is_named_and_not_retried(room_world):
    """Project Home revokes the connection (the room answers 403): name it, stop, and never show stale as live."""
    store, fx, clock, client, service, cards = room_world
    save_room(store)
    fx.answers = healthy_room(cards=[good_card()])
    assert client.snapshot(PROVIDER_ID).error_class is None

    fx.answers = {"/room": raw({"error": "revoked"}, status=403)}
    revoked = client.snapshot(PROVIDER_ID)
    assert revoked.error_class == "auth_failed"                   # the revocation is named, not swallowed
    assert revoked.stale is True and revoked.cards                # old content only, and labelled stale
    assert revoked.last_good_at is not None

    after_first = len(fx.calls)
    again = client.snapshot(PROVIDER_ID)                          # inside the back-off window
    assert again.error_class == "auth_failed"
    assert len(fx.calls) == after_first                           # no silent retry while backing off

    room = service.rooms()[0]
    assert room["reachable"] is False and room["error_class"] == "auth_failed"

    env = service.card(room_card_id(PROVIDER_ID, "finds"))
    assert env["freshness"] == "stale" and env["source_state"] == "needs_attention"
    assert env["evidence"]["error_class"] == "auth_failed"        # never shown as healthy or current


def test_room0_a_removed_provider_is_not_served_from_a_stale_snapshot(room_world):
    """Worlds drops its own reference: the room is gone, nothing is sent, and the cached snapshot is not served."""
    store, fx, clock, client, service, cards = room_world
    save_room(store)
    fx.answers = healthy_room(cards=[good_card()])
    assert client.snapshot(PROVIDER_ID).error_class is None       # a good snapshot is now held in memory

    before = len(fx.calls)
    store.delete("provider", PROVIDER_ID)
    assert client.snapshot(PROVIDER_ID) is None                   # gone, not answered from the cache
    assert service.card(room_card_id(PROVIDER_ID, "finds")) is None
    assert service.providers() == [] and service.rooms() == [] and service.home_items() == []
    assert len(fx.calls) == before                                # nothing was sent after removal


# -------------------------------------------------------- synthetic-only, read-only, no live Project Home


def test_room0_runs_synthetic_and_read_only_reaching_no_live_project_home(room_world):
    """Every read is a fixture GET; the live seam is never entered; the address is a reserved placeholder."""
    store, fx, clock, client, service, cards = room_world
    save_room(store)
    fx.answers = healthy_room(cards=[good_card()], needs=[{"id": "n1", "title": "Please look", "why": "synthetic"}],
                              actions=[ack_action_doc()])
    with _NoDial():
        service.home_items()
        service.rooms()
        service.needs()
        service.candidates(PROVIDER_ID)
    assert fx.calls and all(c["effect"] == "read" and c["method"] == "GET" for c in fx.calls)
    provider = store.get("provider", PROVIDER_ID)
    assert provider.base_url == BASE_URL and provider.base_url.endswith(".lan.example")   # reserved, never live
    assert provider.principal_id == PRINCIPAL                                            # the recipe's placeholder


# -------------------------------------------------------- inherited Stage C condition 1: fail closed (must pass)


def _room_dispatch_env(tmp_path, *, verifier=None):
    """A room/0 provider plus a C3 dispatcher; the room's writes go to a recorder, never a socket."""
    pytest.importorskip("fastapi")                                 # authn imports it; without it these are NOT RUN
    from personal_world.worlds.db import Database
    from personal_world.worlds.dispatcher import Dispatcher

    clock = Clock()
    store = ConfigStore(tmp_path / "cfg")
    room_fx = RoomFixture()
    room_fx.answers = healthy_room(cards=[good_card()], actions=[ack_action_doc()])
    save_room(store)
    client = Room0Client(store, room_fx, clock=clock, ttl_s=0)
    rooms = RoomService(store, client, clock=clock)
    writes = []

    def write_send(provider, request, *, effect):
        writes.append({"method": request.method, "path": request.path, "effect": effect})
        return RawResponse(200, body=b'{"ok": true, "summary": "synthetic"}')

    db = Database.in_dir(tmp_path / "data")
    dispatcher = Dispatcher(db, store, send=write_send, clock=clock, project_home_verifier=verifier)
    return store, rooms, dispatcher, room_fx, writes, clock


def _owner(clock):
    from personal_world.worlds.authn import Principal
    return Principal("owner", "owner", session_hash="h", step_up_at=clock(), via="session")


def test_c1_room0_a_project_home_answer_without_a_verifier_is_never_approved(tmp_path):
    """With no verifier wired, a room answer carrying a Project Home approval id is refused before anything is written.

    This is the room/0 form of the contract's 403 (dispatcher.py:277-278 raises before the write transaction;
    room_routes.py:76 maps NotPermitted to 403). Fail closed: pending stays pending, nothing reaches the room.
    """
    from personal_world.worlds.dispatcher import NotPermitted

    store, rooms, d, room_fx, writes, clock = _room_dispatch_env(tmp_path)
    owner = _owner(clock)
    action = rooms.adopt(PROVIDER_ID, "ack-build")                 # owner adopts a room action; sends nothing
    assert action is not None and action.exposed is False and action.approval == "always" and action.idempotency == "required"

    with pytest.raises(NotPermitted):
        rooms.answer(PROVIDER_ID, "ack-build", {"note": "ok"}, owner, d, project_home_approval_id="ph-approval-1")

    assert writes == []                                            # nothing reached the room
    rows = d._db.conn().execute("SELECT state, authority FROM authorizations").fetchall()
    assert [r["state"] for r in rows] == ["pending"] and rows[0]["authority"] is None
    assert d._db.conn().execute("SELECT COUNT(*) AS n FROM executions").fetchone()["n"] == 0


def test_c1_room0_the_owner_cannot_approve_a_project_home_action_in_worlds(tmp_path):
    """No Project Home approval id at all: the owner's own approve is refused for an externally governed room."""
    from personal_world.worlds.dispatcher import NotPermitted

    store, rooms, d, room_fx, writes, clock = _room_dispatch_env(tmp_path)
    owner = _owner(clock)
    assert rooms.adopt(PROVIDER_ID, "ack-build") is not None

    with pytest.raises(NotPermitted):
        rooms.answer(PROVIDER_ID, "ack-build", {"note": "ok"}, owner, d)   # no project_home_approval_id

    assert writes == []
    rows = d._db.conn().execute("SELECT state FROM authorizations").fetchall()
    assert [r["state"] for r in rows] == ["pending"]


def test_c1_room0_a_verifier_that_does_not_confirm_leaves_it_unapproved(tmp_path):
    """Even a wired verifier that refuses (the shape of a Project Home 403) leaves the action unapproved."""
    from personal_world.worlds.dispatcher import NotPermitted

    seen = []
    store, rooms, d, room_fx, writes, clock = _room_dispatch_env(
        tmp_path, verifier=lambda aid, row: seen.append(aid) or False)
    owner = _owner(clock)
    assert rooms.adopt(PROVIDER_ID, "ack-build") is not None

    with pytest.raises(NotPermitted):
        rooms.answer(PROVIDER_ID, "ack-build", {"note": "ok"}, owner, d, project_home_approval_id="ph-denied")

    assert seen == ["ph-denied"] and writes == []
    rows = d._db.conn().execute("SELECT state FROM authorizations").fetchall()
    assert [r["state"] for r in rows] == ["pending"]


# -------------------------------------- inherited Stage C conditions 2 and 3: pin the gaps, never relax them


def _stage_c_fn(name: str, source: str | None = None) -> ast.FunctionDef | None:
    tree = ast.parse(source if source is not None else _STAGE_C.read_text(encoding="utf-8"))
    return next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None)


def _xfail_pin(name: str, source: str | None = None) -> tuple[bool, bool]:
    """(strict, names_a_raises) for ``name`` in the sibling Stage C file. A pin is an xfail, not a pass."""
    node = _stage_c_fn(name, source)
    for dec in node.decorator_list if node else ():
        if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "xfail"):
            kw = {k.arg: k.value for k in dec.keywords}
            strict = isinstance(kw.get("strict"), ast.Constant) and kw["strict"].value is True
            return strict, kw.get("raises") is not None
    return False, False


def _is_plain_test(name: str) -> bool:
    """True when ``name`` exists in the sibling Stage C file with no decorator at all (no xfail, skip or skipif)."""
    node = _stage_c_fn(name)
    return node is not None and not node.decorator_list


def test_c2_room0_the_state_proposed_pins_are_plain_tests_now_that_the_gap_is_closed():
    """Action.state exists (d-impl Step 3), so the two pins were flipped: they must run, undecorated, and pass.

    A flipped pin that is still (or again) an xfail/skip would paper the gap over, so that fails here.
    """
    from personal_world.worlds.models import Action

    for name in ("test_c2_a_state_proposed_action_can_exist",
                 "test_c2_a_state_proposed_action_is_inert_at_dispatcher_and_runtime"):
        assert _is_plain_test(name), f"{name} must be a plain test: no xfail, no skip"
    assert "state" in Action.model_fields                         # the gap the pins recorded is closed


def test_c3_room0_the_scope_pins_are_plain_or_strict_as_the_gap_is_closed_or_open():
    """Auth.scope and the scope check before DNS exist, so those two pins are plain tests; the label pin is still open."""
    from personal_world.worlds.models import Auth

    for name in ("test_c3_auth_scope_exists_and_none_is_the_legacy_unscoped_state",
                 "test_c3_out_of_scope_capability_fails_before_any_dns_lookup"):
        assert _is_plain_test(name), f"{name} must be a plain test: no xfail, no skip"
    strict, _ = _xfail_pin("test_c3_unscoped_is_labelled_wherever_it_appears")
    assert strict, "the 'unscoped' label pin must stay a strict xfail, not be relaxed to a plain xfail"
    assert "scope" in Auth.model_fields                           # the field §6.1 proposed now exists


def test_c3_room0_a_relaxed_or_dropped_pin_would_be_detected():
    """Negative control: the guard's reading of a pin must tell strict from relaxed from removed."""
    strict_src = "@pytest.mark.xfail(strict=True, raises=ValidationError, reason='r')\ndef t(): ...\n"
    relaxed_src = "@pytest.mark.xfail(reason='r')\ndef t(): ...\n"
    assert _xfail_pin("t", strict_src) == (True, True)
    assert _xfail_pin("t", relaxed_src) == (False, False)
    assert _xfail_pin("gone", strict_src) == (False, False)
    assert _stage_c_fn("t", "def t(): ...\n") is not None and not _stage_c_fn("t", "def t(): ...\n").decorator_list
    assert _stage_c_fn("t", strict_src).decorator_list                # a decorated test is not "plain"
