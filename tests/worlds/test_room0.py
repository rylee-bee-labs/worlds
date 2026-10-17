"""room/0 adapter against a fake room (invented generic cards only): mapping, honesty, adoption, receipts."""
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from personal_world.worlds.authn import SESSION_COOKIE, Principal
from personal_world.worlds.config_store import ConfigStore
from personal_world.worlds.confinement import confined_request
from personal_world.worlds.db import Database
from personal_world.worlds.dispatcher import Dispatcher, NotPermitted
from personal_world.worlds.models import Provider
from personal_world.worlds.production import create_app
from personal_world.worlds.room0 import (
    Room0Client,
    RoomService,
    parse_action,
    parse_card,
    parse_changed,
    parse_need,
    room_card_id,
    status_card_id,
    valid_link,
)

ORIGIN = "https://worlds.example.test"
BOOT = "open-sesame-correct-horse-1"  # pw-safety: synthetic
NOW = 1_900_000_000.0


def iso(t):
    import datetime as dt
    return dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def good_card(**kw):
    d = {"id": "finds", "title": "New finds", "body": "New finds: 3", "link": "/finds", "lane": "personal", "tone": "good_news",
         "freshness": {"observed_at": iso(NOW - 60), "stale_after_s": 3600}}
    d.update(kw)
    return d


class FakeRoom:
    def __init__(self):
        self.descriptor = {"contract": "room/0", "id": "demo", "name": "Demo Room", "icon": "sparkles", "version": "1", "commit": "abc",
                           "status": "healthy", "updated_at": iso(NOW)}
        self.cards = [good_card()]
        self.needs = []
        self.actions = []
        self.receipt = None
        self.status = {}        # path -> http status override
        self.seen = []          # (method, path, headers)
        self.posts = []
        room = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _send(self, code, body):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                room.seen.append(("GET", self.path, dict(self.headers)))
                if self.path in room.status:
                    return self._send(room.status[self.path], b"{}")
                table = {"/room": room.descriptor, "/room/cards": room.cards, "/room/needs-you": room.needs, "/room/actions": room.actions}
                if self.path in table:
                    return self._send(200, table[self.path])
                return self._send(404, {})

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                room.seen.append(("POST", self.path, dict(self.headers)))
                room.posts.append((self.path, dict(self.headers), body))
                if self.path in room.status:
                    return self._send(room.status[self.path], b"{}")
                return self._send(200, room.receipt if room.receipt is not None else {"action_id": "x", "ok": True, "summary": "done", "changed": ["x"], "at": iso(NOW)})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def headers_of(self, path):
        return [h for m, p, h in self.seen if p == path]


@pytest.fixture
def room():
    r = FakeRoom()
    yield r
    r.stop()


def make_provider(room, **kw):
    d = dict(id="demo", name="Demo", kind="room0", base_url=room.base_url, network={"lan": True}, governance="worlds",
             public_url="https://demo.example.test", principal_id="person_1", group="life",
             auth={"type": "bearer", "secret_ref": "env:DEMO_ROOM_TOKEN"})
    d.update(kw)
    return Provider(**d)


@pytest.fixture
def env(room, tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_ROOM_TOKEN", "room-token-value-0123456789")
    store = ConfigStore(tmp_path / "cfg")
    store.save("provider", make_provider(room))
    clock = {"t": NOW}
    client = Room0Client(store, clock=lambda: clock["t"], ttl_s=0)
    svc = RoomService(store, client, clock=lambda: clock["t"])
    return store, client, svc, clock, tmp_path


# --------------------------------------------------------------- provider settings

def test_provider_room_fields_validated():
    base = dict(id="r", name="R", kind="room0", base_url="http://127.0.0.1:1")
    assert Provider(**base, principal_id="a-B_9").principal_id == "a-B_9"
    for bad in ("", "a b", "x" * 65, "a/b", "a\r\nX: y", "é"):
        with pytest.raises(ValidationError):
            Provider(**base, principal_id=bad)
    with pytest.raises(ValidationError):
        Provider(**{**base, "kind": "http"}, principal_id="a")
    with pytest.raises(ValidationError):
        Provider(**{**base, "kind": "http"}, public_url="https://x.test")
    for bad in ("https://x.test/path", "ftp://x.test", "https://u:p@x.test", "https://x.test?q=1", "javascript:alert(1)"):
        with pytest.raises(ValidationError):
            Provider(**base, public_url=bad)
    assert Provider(**base).governed_by_project_home() is True                     # room0 defaults to project_home (fail closed)
    assert Provider(**base, governance="worlds").governed_by_project_home() is False
    assert Provider(**base).group == "machine"


def test_worlds_sends_the_principal_header_itself_and_the_token(env, room):
    store, client, svc, clock, _ = env
    client.snapshot("demo")
    for path in ("/room", "/room/cards", "/room/needs-you", "/room/actions"):
        h = {k.lower(): v for k, v in room.headers_of(path)[0].items()}
        assert h["x-worlds-principal"] == "person_1" and h["authorization"] == "Bearer room-token-value-0123456789"


def test_no_principal_setting_means_no_principal_header_and_an_empty_room_is_not_an_error(env, room):
    store, client, svc, clock, _ = env
    store.save("provider", make_provider(room, principal_id=None), etag=store.etag("provider", "demo"))
    room.cards, room.needs = [], []                                              # a room answers nothing personal without a principal
    snap = client.snapshot("demo", force=True)
    assert snap.error_class is None and snap.cards == [] and snap.needs == []
    assert all("x-worlds-principal" not in {k.lower() for k in h} for h in room.headers_of("/room/cards"))
    assert svc.home_items() == [] and svc.needs() == []                          # nothing to show, nothing invented


def test_a_request_can_never_carry_the_principal_header(env, room):
    from personal_world.worlds.models import Request
    with pytest.raises(ValidationError):
        Request(id="demo.r", provider="demo", path="/room", headers={"X-Worlds-Principal": "someone-else"})


# ------------------------------------------------------------------------- cards

def test_a_room_card_becomes_a_c2_envelope(env, room):
    store, client, svc, clock, _ = env
    cid = room_card_id("demo", "finds")
    assert re.fullmatch(r"^[a-z0-9][a-z0-9-]{0,62}$", cid)
    e = svc.card(cid)
    assert set(e) == {"card_id", "source_state", "freshness", "observed_at", "fetched_at", "last_good_at", "values", "meter",
                      "meaning", "evidence"}
    assert e["card_id"] == cid and e["source_state"] == "healthy" and e["freshness"] == "current" and e["meter"] is None
    assert e["values"]["body"] == {"text": "New finds: 3"}
    assert e["values"]["link"] == {"text": "/finds", "raw": "https://demo.example.test/finds"}
    assert e["meaning"]["short"] == "New finds" and "Demo Room" in e["meaning"]["full"]
    assert e["evidence"]["request_id"] == "demo.room" and e["evidence"]["error_class"] is None
    json.dumps(e)


@pytest.mark.parametrize("status,state", [("healthy", "healthy"), ("degraded", "degraded"), ("unhealthy", "needs_attention"),
                                          ("unknown", "unknown"), ("banana", "unknown"), (None, "unknown")])
def test_descriptor_status_maps_to_a_worlds_state(env, room, status, state):
    store, client, svc, clock, _ = env
    room.descriptor["status"] = status
    assert svc.card(room_card_id("demo", "finds"))["source_state"] == state


def test_a_card_past_stale_after_is_stale_never_current(env, room):
    store, client, svc, clock, _ = env
    clock["t"] = NOW + 7200                                                       # stale_after_s is 3600, observed 60s before NOW
    assert svc.card(room_card_id("demo", "finds"))["freshness"] == "stale"
    clock["t"] = NOW + 100
    assert svc.card(room_card_id("demo", "finds"))["freshness"] == "current"


def test_unknown_tone_reads_as_update_and_is_logged_not_dropped(env, room, caplog):
    room.cards = [good_card(tone="urgent!!")]
    with caplog.at_level("WARNING"):
        c = parse_card(room.cards[0])
    assert c.tone == "update" and any("tone" in m for m in caplog.messages)
    store, client, svc, clock, _ = env
    assert len(svc.home_items()) == 1


@pytest.mark.parametrize("link", ["//evil.test/x", "http://evil.test/x", "https://evil.test", "javascript:alert(1)", "finds", "/a\\b",
                                  "/../etc", "/ok\r\nSet-Cookie: x", "/x" + "y" * 600, 5, ["/x"], ""])
def test_links_must_be_same_origin_paths(link):
    assert valid_link(link) is None


@pytest.mark.parametrize("link", ["/finds", "/a/b?c=d", "/x#frag"])
def test_good_links_pass(link):
    assert valid_link(link) == link


def test_an_invalid_link_is_dropped_but_the_card_stays(env, room):
    room.cards = [good_card(link="//evil.test/x")]
    store, client, svc, clock, _ = env
    e = svc.card(room_card_id("demo", "finds"))
    assert "link" not in e["values"] and e["values"]["body"]["text"] == "New finds: 3"
    assert svc.home_items()[0]["view"] == "stat"


def test_without_a_public_url_there_is_no_link_value(env, room):
    store, client, svc, clock, _ = env
    store.save("provider", make_provider(room, public_url=None), etag=store.etag("provider", "demo"))
    assert "link" not in svc.card(room_card_id("demo", "finds"))["values"]


@pytest.mark.parametrize("patch", [{"title": None}, {"title": ""}, {"title": 7}, {"body": 7}, {"freshness": None}, {"freshness": {"observed_at": "yesterday", "stale_after_s": 5}},
                                   {"freshness": {"observed_at": iso(NOW), "stale_after_s": -1}}, {"freshness": {"observed_at": iso(NOW), "stale_after_s": True}}])
def test_a_malformed_card_is_degraded_with_unknown_values_never_faked(env, room, patch):
    room.cards = [good_card(**patch)]
    store, client, svc, clock, _ = env
    e = svc.card(room_card_id("demo", "finds"))
    assert e["source_state"] == "degraded"
    if "title" in patch or "body" in patch:
        assert e["values"] == {"body": {"text": "unknown"}}


def test_cards_without_a_usable_id_are_skipped_and_the_rest_survive(env, room):
    room.cards = [good_card(id=""), {"title": "no id"}, "not a dict", None, 7, good_card(id="ok", title="Fine")]
    store, client, svc, clock, _ = env
    items = svc.home_items()
    assert [i["title"] for i in items] == ["Fine"]


def test_ids_are_stable_valid_and_distinct(env):
    ids = {room_card_id("demo", x) for x in ["a", "A", "a b", "a_b", "a-b", "é", "x" * 300]}
    assert len(ids) == 7 and all(re.fullmatch(r"^[a-z0-9][a-z0-9-]{0,62}$", i) for i in ids)
    assert room_card_id("demo", "a") == room_card_id("demo", "a")
    long_provider = "p" * 63
    assert len(room_card_id(long_provider, "x" * 300)) <= 63 and len(status_card_id(long_provider)) <= 63


def test_home_item_defs_are_display_only_with_the_provider_group(env, room):
    store, client, svc, clock, _ = env
    item = svc.home_items()[0]
    assert set(item) == {"card", "size", "hidden", "title", "icon", "group", "view", "fields", "meter_type"}
    assert item["group"] == "life" and item["view"] == "link" and item["icon"] == "sparkles"
    assert item["fields"] == [{"key": "link", "label": "New finds", "format": "text", "unit": None}]
    blob = json.dumps(item)
    for leak in ("127.0.0.1", "room-token", "/room/cards", "person_1", "demo.room"):
        assert leak not in blob


def test_a_room_icon_must_be_a_plain_slug(env, room):
    room.descriptor["icon"] = "../../x"
    store, client, svc, clock, _ = env
    assert svc.home_items()[0]["icon"] == "circle"


# -------------------------------------------------------------- honesty on failure

def test_unreachable_room_without_history_shows_one_unavailable_card(env, room):
    store, client, svc, clock, _ = env
    room.stop()
    items = svc.home_items()
    assert len(items) == 1 and items[0]["card"] == status_card_id("demo")
    e = svc.card(status_card_id("demo"))
    assert e["source_state"] == "unavailable" and e["freshness"] == "stale" and e["values"]["status"]["text"] == "unreachable"
    assert e["evidence"]["error_class"] == "connection"
    assert svc.rooms()[0]["reachable"] is False and svc.rooms()[0]["last_seen_at"] is None


def test_unreachable_room_keeps_its_last_known_cards_marked_stale(env, room):
    store, client, svc, clock, _ = env
    assert svc.card(room_card_id("demo", "finds"))["freshness"] == "current"
    room.stop()
    clock["t"] += 30
    e = svc.card(room_card_id("demo", "finds"))
    assert e["source_state"] == "unavailable" and e["freshness"] == "stale" and e["values"]["body"]["text"] == "New finds: 3"
    assert e["last_good_at"] is not None and e["fetched_at"] != e["last_good_at"]
    assert svc.rooms()[0]["last_seen_at"] == NOW


def test_one_dead_room_never_blanks_the_others(env, room, tmp_path):
    store, client, svc, clock, _ = env
    dead = FakeRoom()
    dead_url = dead.base_url
    dead.stop()
    store.save("provider", make_provider(room, id="gone", name="Gone", base_url=dead_url, principal_id=None))
    items = svc.home_items()
    assert {i["card"] for i in items} == {room_card_id("demo", "finds"), status_card_id("gone")}


def test_401_is_needs_attention_and_5xx_unavailable_and_garbage_degraded(env, room):
    store, client, svc, clock, _ = env
    for status, state, cls in [(401, "needs_attention", "auth_failed"), (403, "needs_attention", "auth_failed"),
                               (500, "unavailable", "http_5xx"), (404, "degraded", "http_4xx")]:
        room.status = {"/room/cards": status}
        clock["t"] += 400                                                 # past any failure back-off
        e = svc.card(status_card_id("demo"))
        assert (e["source_state"], e["evidence"]["error_class"]) == (state, cls), status
    room.status = {}
    room.cards = {"not": "a list"}
    clock["t"] += 400
    assert svc.card(status_card_id("demo"))["source_state"] == "degraded"
    room.cards = [good_card()]
    room.descriptor = {"contract": "room/9", "name": "X", "status": "healthy"}
    clock["t"] += 400
    e = svc.card(status_card_id("demo"))
    assert e["source_state"] == "degraded" and e["evidence"]["error_class"] == "malformed"


def test_non_json_room_is_malformed(env, room):
    store, client, svc, clock, _ = env
    room.descriptor = None
    snap = client.snapshot("demo", force=True)
    assert snap.error_class == "malformed"


def test_secrets_never_reach_the_envelope(env, room):
    store, client, svc, clock, _ = env
    blob = json.dumps(svc.card(room_card_id("demo", "finds"))) + json.dumps(svc.rooms()) + json.dumps(svc.home_items())
    assert "room-token-value" not in blob and "Bearer" not in blob


# -------------------------------------------------------------------------- needs

def test_needs_map_to_open_actions_with_an_href_only_when_it_is_safe(env, room):
    room.needs = [{"id": "n1", "title": "Pick one", "why": "Two matches", "actions": ["pick"], "link": "/pick", "created_at": iso(NOW - 30)},
                  {"id": "n2", "title": "Look", "why": "", "actions": [], "link": "//evil.test/x", "created_at": iso(NOW - 10)},
                  {"id": "", "title": "bad"}, {"id": "n4", "title": ""}, "junk"]
    store, client, svc, clock, _ = env
    out = svc.needs()
    assert [n["text"] for n in out] == ["Pick one — Two matches", "Look"]
    assert out[0]["action"] == {"kind": "open", "href": "https://demo.example.test/pick"} and out[1]["action"] == {"kind": "open"}
    assert out[0]["source"] == "Demo Room" and out[0]["created_at"] == NOW - 30 and out[0]["id"].startswith("room:demo:")
    assert len({n["id"] for n in out}) == 2


def test_need_parsing_limits():
    n = parse_need({"id": "x", "title": "t" * 500, "why": "w" * 900, "created_at": "nope"})
    assert len(n.title) == 200 and len(n.why) == 400 and n.created_at is None


# ------------------------------------------------------------------ actions / adoption

ACTIONS = [{"id": "refresh", "label": "Refresh now", "input_schema": {"type": "object"}, "default_autonomy": "auto", "writes": False},
           {"id": "mark-seen", "label": "Mark seen", "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}}},
            "default_autonomy": "weird", "writes": True}]


def test_actions_are_candidates_until_the_owner_adopts_them(env, room):
    room.actions = ACTIONS
    store, client, svc, clock, _ = env
    cands = svc.candidates("demo")
    assert [(c["room_action_id"], c["adopted"]) for c in cands] == [("refresh", False), ("mark-seen", False)]
    assert cands[1]["default_autonomy"] == "ask_first"                               # an unknown autonomy is the strictest
    assert store.get("action", cands[0]["action_id"]) is None and room.posts == []   # nothing callable, nothing sent


def test_adoption_creates_a_never_exposed_always_approved_write_action(env, room):
    room.actions = ACTIONS
    store, client, svc, clock, _ = env
    a = svc.adopt("demo", "refresh")                                                   # the room says writes:false: still a write here
    assert (a.exposed, a.approval, a.access, a.idempotency, a.owner_waives_approval) == (False, "always", "write", "required", False)
    req = store.get("request", a.request)
    assert req.method == "POST" and req.path == "/room/actions/refresh" and req.resolved_effect() == "write"
    assert svc.adopt("demo", "refresh").id == a.id                                     # adopting twice is harmless
    assert [c["adopted"] for c in svc.candidates("demo")] == [True, False]
    assert svc.adopt("demo", "nope") is None and svc.adopt("missing", "refresh") is None
    assert room.posts == []


def test_hostile_action_ids_are_rejected_or_neutralised(env, room):
    room.actions = [{"id": "../../etc", "label": "x"}, {"id": "a b", "label": "x"}, {"id": "ok_1.2", "label": "Fine"}, {"id": "a/b", "label": "y"}]
    store, client, svc, clock, _ = env
    assert [c["room_action_id"] for c in svc.candidates("demo")] == ["ok_1.2"]
    assert parse_action({"id": "x", "label": ""}) is None and parse_action({"id": "x"}) is None
    assert parse_action({"id": "x", "label": "L"}).writes is True and parse_action({"id": "x", "label": "L"}).default_autonomy == "ask_first"


def run(store, tmp_path, monkeypatch=None, governed=None, step=True):
    db = Database.in_dir(tmp_path / "data")
    kw = {} if governed is None else {"governed_by_project_home": governed}
    d = Dispatcher(db, store, send=confined_request, **kw)
    o = Principal("owner", "owner", step_up_at=time.time() if step else None, via="session")
    return d, o


def test_an_adopted_action_runs_through_the_dispatcher_like_any_write(env, room, tmp_path):
    room.actions = ACTIONS
    store, client, svc, clock, _ = env
    a = svc.adopt("demo", "mark-seen")
    d, o = run(store, tmp_path)
    auth = d.request_authorization(o, a.id, {"n": 3}, "key-1")
    assert auth["state"] == "pending"                                                    # never auto-approved
    assert room.posts == []
    r = d.execute(o, d.approve(o, auth["id"])["id"])
    assert r["state"] == "SUCCEEDED" and r["evidence"]["summary"] == "done"
    path, headers, body = room.posts[0]
    h = {k.lower(): v for k, v in headers.items()}
    assert path == "/room/actions/mark-seen" and h["idempotency-key"] == "key-1" and h["x-worlds-principal"] == "person_1"
    assert h["authorization"].startswith("Bearer ") and json.loads(body) == {"n": 3}
    assert len(room.posts) == 1


def test_a_missing_idempotency_key_is_refused_for_room_actions(env, room, tmp_path):
    room.actions = ACTIONS
    store, client, svc, clock, _ = env
    a = svc.adopt("demo", "refresh")
    d, o = run(store, tmp_path)
    from personal_world.worlds.dispatcher import BadRequest
    with pytest.raises(BadRequest):
        d.request_authorization(o, a.id)


@pytest.mark.parametrize("receipt,state", [
    ({"action_id": "x", "ok": True, "summary": "did it", "changed": ["row"], "at": "t"}, "SUCCEEDED"),
    ({"action_id": "x", "ok": False, "summary": "refused", "changed": [], "at": "t"}, "FAILED"),
    ({"action_id": "x", "ok": False, "summary": "half done", "changed": ["row"], "at": "t"}, "UNKNOWN"),
    ({"action_id": "x", "ok": False, "summary": "?", "at": "t"}, "UNKNOWN"),
    ({"summary": "no ok field"}, "UNKNOWN"), ({"ok": "yes"}, "UNKNOWN"), ([1, 2], "UNKNOWN")])
def test_the_rooms_own_receipt_decides_the_outcome(env, room, tmp_path, receipt, state):
    room.actions = ACTIONS
    room.receipt = receipt
    store, client, svc, clock, _ = env
    a = svc.adopt("demo", "refresh")
    d, o = run(store, tmp_path)
    r = d.execute(o, d.approve(o, d.request_authorization(o, a.id, None, "k")["id"])["id"])
    assert r["state"] == state


def test_an_unreadable_receipt_is_unknown_never_a_silent_success(env, room, tmp_path):
    room.actions = ACTIONS
    room.receipt = b"not json"
    store, client, svc, clock, _ = env
    a = svc.adopt("demo", "refresh")
    d, o = run(store, tmp_path)
    assert d.execute(o, d.approve(o, d.request_authorization(o, a.id, None, "k")["id"])["id"])["state"] == "UNKNOWN"


def test_ask_first_without_a_room_approval_token_fails_closed_at_the_room(env, room, tmp_path):
    room.actions = ACTIONS
    room.status = {"/room/actions/refresh": 403}
    store, client, svc, clock, _ = env
    a = svc.adopt("demo", "refresh")
    d, o = run(store, tmp_path)
    r = d.execute(o, d.approve(o, d.request_authorization(o, a.id, None, "k")["id"])["id"])
    assert r["state"] == "FAILED" and r["status_code"] == 403                            # the room refused: it did not run


def test_a_room_without_explicit_worlds_governance_cannot_be_approved_in_worlds(env, room, tmp_path):
    room.actions = ACTIONS
    store, client, svc, clock, _ = env
    a = svc.adopt("demo", "refresh")
    store.save("provider", make_provider(room, governance=None), etag=store.etag("provider", "demo"))   # room0 default: project_home
    d, o = run(store, tmp_path)
    auth = d.request_authorization(o, a.id, None, "k")
    with pytest.raises(NotPermitted):
        d.approve(o, auth["id"])


# ----------------------------------------------------------- production end to end

def prod(room, tmp_path, monkeypatch):
    monkeypatch.setenv("PW_TEST_BOOTSTRAP", BOOT)
    monkeypatch.setenv("DEMO_ROOM_TOKEN", "room-token-value-0123456789")
    cfg, data = tmp_path / "cfg", tmp_path / "data"
    cfg.mkdir()
    (cfg / "owner.yaml").write_text(yaml.safe_dump({"schema_version": 1, "public_origin": ORIGIN,
                                                    "bootstrap": {"enabled": True, "secret_ref": "env:PW_TEST_BOOTSTRAP"}}))
    s = ConfigStore(cfg)
    s.save("provider", make_provider(room))
    app = create_app(cfg, data, maintenance_interval=3600)
    c = TestClient(app, base_url=ORIGIN, follow_redirects=False)
    assert c.post("/api/auth/bootstrap", json={"token": BOOT}, headers={"Origin": ORIGIN}).status_code == 200
    h = {"Origin": ORIGIN, "X-CSRF-Token": app.state.auth.csrf_token(c.cookies.get(SESSION_COOKIE))}
    return app, c, h


def test_home_cards_and_needs_come_from_the_room_in_the_production_app(room, tmp_path, monkeypatch):
    room.needs = [{"id": "n1", "title": "Pick one", "why": "Two matches", "actions": [], "created_at": iso(NOW)}]
    app, c, h = prod(room, tmp_path, monkeypatch)
    home = c.get("/api/boards/home").json()
    assert [i["title"] for i in home["items"]] == ["New finds"] and home["items"][0]["group"] == "life"
    e = c.get(f"/api/cards/{home['items'][0]['card']}").json()
    assert e["values"]["body"]["text"] == "New finds: 3" and e["source_state"] == "healthy"
    assert [n["text"] for n in c.get("/api/needs-you").json()] == ["Pick one — Two matches"]
    assert c.get("/api/cards/r-nope-000000").status_code == 404
    rooms = c.get("/api/rooms").json()
    assert rooms[0]["id"] == "demo" and rooms[0]["reachable"] is True and rooms[0]["governance"] == "worlds"


def test_room_routes_are_owner_only_and_adoption_needs_csrf(room, tmp_path, monkeypatch):
    room.actions = ACTIONS
    app, c, h = prod(room, tmp_path, monkeypatch)
    anon = TestClient(app, base_url=ORIGIN)
    assert anon.get("/api/rooms").status_code == 401
    assert anon.post("/api/rooms/demo/actions/refresh/adopt").status_code == 401
    assert c.post("/api/rooms/demo/actions/refresh/adopt").status_code == 403                      # session, no CSRF
    tok = c.post("/api/agent-tokens", json={"name": "b", "scopes": ["*"]}, headers=h).json()["token"]
    ag = {"Authorization": f"Bearer {tok}"}
    assert anon.get("/api/rooms", headers=ag).status_code == 403 and anon.post("/api/rooms/demo/actions/refresh/adopt", headers=ag).status_code == 403
    assert [x["adopted"] for x in c.get("/api/rooms/demo/actions").json()] == [False, False]
    ok = c.post("/api/rooms/demo/actions/refresh/adopt", headers=h)
    assert ok.status_code == 200 and ok.json()["exposed"] is False and ok.json()["approval"] == "always"
    assert c.post("/api/rooms/demo/actions/nope/adopt", headers=h).status_code == 404
    assert c.get("/api/rooms/missing/actions").status_code == 404
    assert any(a["id"].startswith("demo-refresh-") for a in c.get("/api/actions").json())


def test_an_unreachable_room_does_not_blank_home_in_production(room, tmp_path, monkeypatch):
    app, c, h = prod(room, tmp_path, monkeypatch)
    assert len(c.get("/api/boards/home").json()["items"]) == 1
    room.stop()
    app.state.rooms._client._ttl = 0                                   # the short cache has expired
    items = c.get("/api/boards/home").json()["items"]
    assert len(items) == 1
    e = c.get(f"/api/cards/{items[0]['card']}").json()
    assert e["freshness"] == "stale" and e["source_state"] == "unavailable"


# ----------------------------------------------- Home stays fast on a bad day (review #242)

def _blackhole():
    """Accepts connections and never answers."""
    import socket
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    conns = []

    def run():
        while True:
            try:
                conns.append(srv.accept()[0])
            except OSError:
                return

    threading.Thread(target=run, daemon=True).start()
    return srv


def test_one_blackholed_room_and_three_live_ones_every_room_present_and_home_stays_fast(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_ROOM_TOKEN", "room-token-value-0123456789")
    live = [FakeRoom() for _ in range(3)]
    hole = _blackhole()
    try:
        store = ConfigStore(tmp_path / "cfg")
        for i, r in enumerate(live):
            r.cards = [good_card(id=f"c{i}", title=f"Live {i}")]
            store.save("provider", make_provider(r, id=f"live{i}", name=f"Live {i}", principal_id=None, timeout_s=5))
        store.save("provider", Provider(id="hole", name="Hole", kind="room0", base_url=f"http://127.0.0.1:{hole.getsockname()[1]}",
                                        network={"lan": True}, governance="worlds", timeout_s=5,
                                        auth={"type": "bearer", "secret_ref": "env:DEMO_ROOM_TOKEN"}))
        svc = RoomService(store, Room0Client(store))
        t0 = time.monotonic()
        first = svc.home_items()
        assert time.monotonic() - t0 < 3.0                                       # not the 5 s provider timeout
        titles = {i["title"] for i in first}
        assert {"Live 0", "Live 1", "Live 2"} <= titles and len(first) == 4      # the blackholed room is PRESENT, as unavailable
        time.sleep(5.5)                                                          # let the background fetch finish and fail
        t1 = time.monotonic()
        again = svc.home_items()
        needs = svc.needs()
        assert time.monotonic() - t1 < 1.0 and len(again) == 4 and isinstance(needs, list)   # failures are cached: no new 5 s wait
        ids = {i["card"] for i in again}
        assert status_card_id("hole") in ids
        assert svc.card(status_card_id("hole"))["source_state"] == "unavailable"
        assert all(r["id"] for r in svc.rooms()) and len(svc.rooms()) == 4
    finally:
        hole.close()
        [r.stop() for r in live]


def test_failures_are_cached_with_a_doubling_back_off_and_recover(env, room):
    store, client, svc, clock, _ = env
    client._ttl = 15
    room.stop()
    first = client.snapshot("demo")
    assert first.error_class == "connection"
    clock["t"] += 10
    assert client.snapshot("demo") is first                                       # inside the 30 s back-off: no new attempt
    clock["t"] += 25
    second = client.snapshot("demo")
    assert second is not first                                                    # back-off over: tried again, failed again
    assert client._fails["demo"][0] == 2
    assert client._fails["demo"][1] - clock["t"] > 55                              # now ~60 s
    for _ in range(12):
        clock["t"] += 400
        client.snapshot("demo")
    assert client._fails["demo"][1] - clock["t"] <= client.FAIL_BACKOFF_MAX_S + 1  # capped at 5 minutes


def test_a_room_that_comes_back_clears_its_back_off(env, room):
    store, client, svc, clock, _ = env
    room.status = {"/room": 500}
    client.snapshot("demo")
    assert "demo" in client._fails
    room.status = {}
    clock["t"] += 400
    assert client.snapshot("demo").error_class is None and "demo" not in client._fails


def test_a_card_request_asks_only_its_own_room(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_ROOM_TOKEN", "room-token-value-0123456789")
    a, b = FakeRoom(), FakeRoom()
    try:
        store = ConfigStore(tmp_path / "cfg")
        store.save("provider", make_provider(a, id="alpha", name="Alpha"))
        store.save("provider", make_provider(b, id="beta", name="Beta"))
        svc = RoomService(store, Room0Client(store))
        assert svc.card(room_card_id("alpha", "finds"))["values"]["body"]["text"] == "New finds: 3"
        assert b.seen == []                                                       # the other room was never contacted
        assert svc.card("r-nobody-finds-000000") is None and b.seen == []
    finally:
        a.stop()
        b.stop()


def test_a_request_does_not_queue_behind_a_slow_fetch(env, room, monkeypatch):
    store, client, svc, clock, _ = env
    client.snapshot("demo")                                                        # known state exists
    gate = threading.Event()
    real = client._fetch
    monkeypatch.setattr(client, "_fetch", lambda provider: (gate.wait(3), real(provider))[1])
    t = threading.Thread(target=lambda: client.snapshot("demo", force=True))
    t.start()
    time.sleep(0.1)
    t0 = time.monotonic()
    snap = client.snapshot("demo", force=True)                                     # the lock is held: serve what we know
    assert time.monotonic() - t0 < 1.0 and snap is not None
    gate.set()
    t.join()


def test_a_room_with_no_history_that_is_still_loading_is_explicitly_unavailable(env, monkeypatch):
    store, client, svc, clock, _ = env
    svc.SNAPSHOT_BUDGET_S = 0.2
    release = threading.Event()
    monkeypatch.setattr(client, "_fetch", lambda provider: (release.wait(2), client._unavailable(provider, "slow"))[1])
    items = svc.home_items()
    release.set()
    assert [i["card"] for i in items] == [status_card_id("demo")]


def test_adopted_ids_cannot_collide_for_lookalike_room_action_ids(env, room):
    room.actions = [{"id": "a.b", "label": "One"}, {"id": "a:b", "label": "Two"}, {"id": "a-b", "label": "Three"}, {"id": "a_b", "label": "Four"}]
    store, client, svc, clock, _ = env
    ids = {svc.adopt("demo", x).id for x in ("a.b", "a:b", "a-b", "a_b")}
    assert len(ids) == 4 and all(re.fullmatch(r"^[a-z0-9][a-z0-9-]{0,62}$", i) for i in ids)


def test_adopt_with_an_invalid_id_is_a_plain_400_and_a_leftover_request_is_reused(room, tmp_path, monkeypatch):
    room.actions = ACTIONS
    app, c, h = prod(room, tmp_path, monkeypatch)
    for bad in ("..", "a b", "a%00b", "x" * 200):
        r = c.post(f"/api/rooms/demo/actions/{bad}/adopt", headers=h)
        assert r.status_code in (400, 404) and "Traceback" not in r.text, bad
    r = c.post("/api/rooms/demo/actions/..%2F..%2Fx/adopt", headers=h)
    assert r.status_code in (400, 404)
    # a half-finished earlier adoption left the request behind: adopting again completes it
    svc = app.state.rooms
    rid, aid = svc._ids("demo", "refresh")
    from personal_world.worlds.models import Request as Req
    app.state.store.save("request", Req(id=rid, provider="demo", method="POST", path="/room/actions/refresh", ttl_s=0))
    ok = c.post("/api/rooms/demo/actions/refresh/adopt", headers=h)
    assert ok.status_code == 200 and app.state.store.get("action", aid) is not None


# ------------------------------------------------------------- review #242 follow-ups

def test_long_provider_ids_keep_card_and_status_lookups_consistent(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_ROOM_TOKEN", "room-token-value-0123456789")
    r = FakeRoom()
    try:
        store = ConfigStore(tmp_path / "cfg")
        pid = "livingroom-thermostat-1x-extra-long-id"                 # > 20 and > 30 chars
        assert len(pid) > 30
        store.save("provider", make_provider(r, id=pid, name="Thermostat"))
        svc = RoomService(store, Room0Client(store, ttl_s=0))
        item = svc.home_items()[0]
        assert svc.card(item["card"]) is not None                       # the id Home lists resolves
        r.stop()
        svc._client._cache.clear()
        svc._client._fails.clear()
        items = svc.home_items()                                          # now only the status card (it has a 40-char id part)
        assert svc.card(items[0]["card"]) is not None
        for room_id in ("a" * 22, "b" * 40, "c" * 300):
            cid = room_card_id(pid, room_id)
            assert re.fullmatch(r"^[a-z0-9][a-z0-9-]{0,62}$", cid) and cid.startswith("r-")
    finally:
        r.stop()


def test_a_cached_snapshot_served_after_its_ttl_is_marked_stale(env, room):
    store, client, svc, clock, _ = env
    client._ttl = 15
    svc.SNAPSHOT_BUDGET_S = 0.05
    client.snapshot("demo")                                               # fresh, cached
    clock["t"] += 100                                                     # well past the TTL
    import threading as _t
    gate = _t.Event()
    real = client._fetch
    client._fetch = lambda provider: (gate.wait(2), real(provider))[1]    # the refresh is slow: the budget serves the cache
    e = svc.card(room_card_id("demo", "finds"))
    gate.set()
    assert e["freshness"] == "stale"


@pytest.mark.parametrize("bad", [".", "..", "...", ":", "-", "a..b", "../x"])
def test_dot_only_and_dotdot_action_ids_are_not_actions(env, room, bad):
    room.actions = [{"id": bad, "label": "x"}, {"id": "fine", "label": "Fine"}]
    store, client, svc, clock, _ = env
    assert [c["room_action_id"] for c in svc.candidates("demo")] == ["fine"]
    with pytest.raises(ValueError):
        svc.adopt("demo", bad)


def test_a_leftover_request_is_reused_only_if_it_is_exactly_this_actions_own(env, room):
    from personal_world.worlds.config_store import ConfigInvalid
    from personal_world.worlds.models import Request as Req
    room.actions = ACTIONS
    store, client, svc, clock, _ = env
    rid, aid = svc._ids("demo", "refresh")
    store.save("request", Req(id=rid, provider="demo", method="POST", path="/room/actions/other-thing", ttl_s=0))
    with pytest.raises(ConfigInvalid):
        svc.adopt("demo", "refresh")
    assert store.get("action", aid) is None
    store.delete("request", rid)
    store.save("request", Req(id=rid, provider="demo", method="POST", path="/room/actions/refresh", body={"sneaky": 1}, ttl_s=0))
    with pytest.raises(ConfigInvalid):
        svc.adopt("demo", "refresh")                                      # a fixed body would override the caller's params
    store.delete("request", rid)
    store.save("request", Req(id=rid, provider="demo", method="POST", path="/room/actions/refresh", ttl_s=0))
    assert svc.adopt("demo", "refresh").id == aid                         # exactly ours: reused


# ------------------------------------------------- typed choices + answering a need (C8)

CHOICE_ACTION = {"id": "pick", "label": "Pick a match", "input_schema": {"type": "object"},
                 "default_autonomy": "ask_first", "writes": True, "allow_text": True,
                 "choices": [{"value": "a1", "label": "Match A"}, {"value": "b2", "label": "Match B"}]}


def test_action_with_choices_prefills_request(env, room, tmp_path):
    room.actions = [CHOICE_ACTION]
    store, client, svc, clock, _ = env
    cands = svc.candidates("demo")
    assert len(cands) == 1
    assert cands[0]["allow_text"] is True
    assert cands[0]["choices"] == [{"value": "a1", "label": "Match A"}, {"value": "b2", "label": "Match B"}]
    svc.adopt("demo", "pick")
    d, o = run(store, tmp_path)
    receipt = svc.answer("demo", "pick", {"choice": "a1"}, o, d)
    assert receipt["state"] == "SUCCEEDED" and receipt["authority"] == "worlds_owner"
    assert len(room.posts) == 1                                            # at most one network attempt
    path, headers, body = room.posts[0]
    assert path == "/room/actions/pick"
    assert json.loads(body) == {"choice": "a1"}                           # the chosen value reached the adopted request


def test_action_choices_are_sanitised_at_the_boundary():
    doc = {"id": "pick", "label": "Pick", "allow_text": "yes", "choices": [
        {"value": "  keep  ", "label": "  Keep me  "}, "plain", 7, {"value": ""}, {"value": "   "},
        {"label": "no value"}, {"value": "keep"}, {"value": "v" * 500}, "plain", None, ["nested"],
        {"value": "ok", "label": 9}]}
    a = parse_action(doc)
    assert [c.value for c in a.choices] == ["keep", "plain", "v" * 120, "ok"]   # trimmed, cut, deduped, junk dropped
    assert a.choices[0].label == "Keep me" and a.choices[1].label is None
    assert a.choices[3].label is None                                      # a non-string label is not a label
    assert a.allow_text is False                                           # 'yes' is not literal True: fail closed
    assert parse_action({"id": "p", "label": "P", "allow_text": True}).allow_text is True
    assert parse_action({"id": "p", "label": "P", "allow_text": 1}).allow_text is False
    for junk in ("nope", None, {"a": 1}, 7):
        assert parse_action({"id": "p", "label": "P", "choices": junk}).choices == ()
    many = parse_action({"id": "p", "label": "P", "choices": [{"value": f"v{i}"} for i in range(50)]})
    assert len(many.choices) == 20 and [c.value for c in many.choices] == [f"v{i}" for i in range(20)]
    plain = parse_action({"id": "p", "label": "P"})
    assert plain.choices == () and plain.allow_text is False               # missing means none, fail closed


def test_an_unadopted_room_action_cannot_be_answered(env, room, tmp_path):
    room.actions = ACTIONS
    store, client, svc, clock, _ = env
    d, o = run(store, tmp_path)
    assert svc.answer("demo", "refresh", None, o, d) is None                # the room offers it, but it is not adopted
    assert svc.answer("demo", "nope", None, o, d) is None                   # the room has no such action
    assert d.list_receipts() == [] and room.posts == []                    # refused, nothing authorised, nothing sent
    with pytest.raises(ValueError):
        svc.answer("demo", "../x", None, o, d)


def test_answering_a_need_approves_consumes_and_dispatches_once(env, room, tmp_path):
    from personal_world.worlds.dispatcher import NotConsumable
    room.actions = ACTIONS
    store, client, svc, clock, _ = env
    assert svc.adopt("demo", "refresh").id
    d, o = run(store, tmp_path)
    receipt = svc.answer("demo", "refresh", None, o, d)
    assert receipt["state"] == "SUCCEEDED" and receipt["authority"] == "worlds_owner"
    assert d.get_authorization(receipt["authorization_id"])["state"] == "consumed"
    assert len(room.posts) == 1
    with pytest.raises(NotConsumable):                                      # one authorization, one dispatch, never a re-send
        d.execute(o, receipt["authorization_id"])
    assert len(room.posts) == 1


def test_the_answer_route_runs_the_adopted_action_once(room, tmp_path, monkeypatch):
    room.actions = ACTIONS
    app, c, h = prod(room, tmp_path, monkeypatch)
    assert c.post("/api/rooms/demo/actions/refresh/adopt", headers=h).status_code == 200
    assert c.post("/api/auth/step-up", json={"token": BOOT}, headers=h).status_code == 200
    r = c.post("/api/rooms/demo/actions/refresh/answer", json={"params": {"n": 3}}, headers=h)
    assert r.status_code == 200 and r.json()["state"] == "SUCCEEDED"
    assert len(room.posts) == 1 and json.loads(room.posts[0][2]) == {"n": 3}
    sent = len(room.posts)
    assert c.post("/api/rooms/demo/actions/mark-seen/answer", json={}, headers=h).status_code == 404
    assert c.post("/api/rooms/demo/actions/nope/answer", json={}, headers=h).status_code == 404
    assert len(room.posts) == sent


# ----------------------------------------------------------- the /changed ping (ROOM rule 15)

def test_room_changed_ping_invalidates_cache(env, room):
    store, client, svc, clock, _ = env
    client._ttl = 15
    first = client.snapshot("demo")
    hits = len(room.seen)
    assert first is not None and hits > 0
    assert client.snapshot("demo") is first and len(room.seen) == hits        # cache warm: no second read
    room.cards = [good_card(title="Changed", body="Changed body")]
    assert client.invalidate("demo") is True                                 # the ping: invalidate only
    assert len(room.seen) == hits                                            # the ping sent NOTHING to the room
    assert client._cache.get("demo") is None and client._good.get("demo") is None and "demo" not in client._fails
    fresh = client.snapshot("demo")                                          # the next read refetches
    assert fresh is not first and len(room.seen) > hits
    assert [c.title for c in fresh.cards] == ["Changed"]


def test_a_valid_changed_ping_is_recognised():
    p = parse_changed({"contract": "room/0", "changed": True, "provider_room_id": "demo", "at": iso(NOW)})
    assert p is not None and p.changed is True and p.provider_room_id == "demo" and p.at == NOW
    assert parse_changed(b'{"contract": "room/0", "changed": true}') is not None


@pytest.mark.parametrize("body", [None, 7, [], "not json", b"", b"{oops", b"not-json-at-all",
                                  {"contract": "room/0"}, {"contract": "room/9", "changed": True}, {"changed": True},
                                  {"contract": "room/0", "changed": False}, {"contract": "room/0", "changed": "true"},
                                  {"contract": "room/0", "changed": 1}])
def test_a_malformed_changed_ping_is_ignored(body):
    assert parse_changed(body) is None


def test_a_changed_ping_with_an_unbounded_id_is_a_ping_but_keeps_no_id():
    p = parse_changed({"contract": "room/0", "changed": True, "provider_room_id": "x" * 500})
    assert p is not None and p.provider_room_id is None


def test_the_changed_route_invalidates_and_sends_nothing_to_the_room(room, tmp_path, monkeypatch):
    app, c, h = prod(room, tmp_path, monkeypatch)
    client = app.state.rooms._client
    client._ttl = 15
    client.snapshot("demo")
    hits = len(room.seen)
    r = c.post("/api/rooms/demo/changed", headers=h)
    assert r.status_code == 200 and r.json() == {"id": "demo", "invalidated": True}
    assert len(room.seen) == hits                                            # the route sent NOTHING to the room
    assert c.post("/api/rooms/missing/changed", headers=h).status_code == 404
    anon = TestClient(app, base_url=ORIGIN)
    assert anon.post("/api/rooms/demo/changed").status_code == 401
    assert c.post("/api/rooms/demo/changed").status_code == 403              # session, no CSRF
