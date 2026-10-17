"""Regression tests for the #233 review findings."""
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from personal_world.worlds import confinement
from personal_world.worlds.config_store import ConfigStore, EtagMismatch
from personal_world.worlds.confinement import ConfinementError
from personal_world.worlds.mapping import resolve
from personal_world.worlds.models import Assertion, Card, Provider, Request
from personal_world.worlds.reference_provider import ReferenceServer, reference_send
from personal_world.worlds.server import build_app

from .conftest import add_card, add_request, ok


# 2: production app sends only through confinement
def test_production_app_uses_confined_request(tmp_path):
    app = build_app(tmp_path / "cfg", principal_dependency=lambda: "owner")
    assert app.state.runner._send is confinement.confined_request


def test_override_is_explicit_only(tmp_path):
    def marker(*a, **k):
        return None
    app = build_app(tmp_path / "cfg", principal_dependency=lambda: "owner", send_override=marker)
    assert app.state.runner._send is marker


# 3: header allow-list
@pytest.mark.parametrize("h", ["Host", "Transfer-Encoding", "Content-Length", "Forwarded", "X-Forwarded-For",
                               "X-Forwarded-Host", "X-Api-Key", "Authorization", "Cookie", "Connection"])
def test_headers_outside_allow_list_rejected(h):
    with pytest.raises(ValidationError):
        Request(id="p.r", provider="p", path="/x", headers={h: "v"})


@pytest.mark.parametrize("h", ["Accept", "accept-language", "Content-Type", "User-Agent", "If-None-Match",
                               "If-Modified-Since", "Idempotency-Key"])
def test_allowed_headers_accepted(h):
    Request(id="p.r", provider="p", path="/x", headers={h: "v"})


def test_header_control_chars_rejected():
    with pytest.raises(ValidationError):
        Request(id="p.r", provider="p", path="/x", headers={"Accept": "a\r\nX: y"})


# 4: missing vs empty
def test_resolve_distinguishes_missing_from_empty():
    assert resolve({"items": []}, "$.items[*]").found is True
    assert resolve({"items": []}, "$.items[*]").values == []
    assert resolve({}, "$.items[*]").found is False
    assert resolve(None, "$.items[*]").found is False
    assert resolve({"items": [{}]}, "$.items[*].name").found is False
    assert resolve({"items": [{"name": "a"}, {}]}, "$.items[*].name").values == ["a"]
    assert resolve({"a": 1}, "$.a.b").found is False


def test_missing_wildcard_card_value_is_unknown_not_none(store, send):
    from personal_world.worlds.cards import CardService
    from personal_world.worlds.runner import Runner
    add_request(store, ttl_s=0)
    add_card(store, fields=[{"path": "$.items[*].name", "label": "Names"}])
    send.responses["/items"] = ok({"other": 1})
    e = CardService(store, Runner(store, send)).build("c1")
    assert e["values"]["names"] == {"text": "unknown"}
    send.responses["/items"] = ok(None)
    e = CardService(store, Runner(store, send)).build("c1")
    assert e["values"]["names"] == {"text": "unknown"}


def test_is_list_assertion_fails_when_path_missing(store, send):
    from personal_world.worlds.runner import Runner
    add_request(store, assertions=[Assertion(path="$.items", is_list=True)])
    send.responses["/items"] = ok({"nothing": 1})
    f = Runner(store, send).fetch("ref.items")
    assert not f.ok and f.error_class == "malformed"
    send.responses["/items"] = ok({"items": []})
    assert Runner(store, send).fetch("ref.items", force=True).ok


# 5: dev host check and reference sender limits
def test_trusted_host_blocks_rebinding(tmp_path):
    app = build_app(tmp_path / "cfg", principal_dependency=lambda: "owner",
                    allowed_hosts=["127.0.0.1", "::1", "localhost"])
    c = TestClient(app, base_url="http://127.0.0.1")
    assert c.get("/healthz").status_code == 200
    assert c.get("/healthz", headers={"Host": "evil.example"}).status_code == 400


def test_reference_sender_refuses_non_reference_or_non_loopback():
    send = reference_send({})
    r = Request(id="p.r", provider="p", path="/x")
    http = Provider(id="p", name="P", kind="http", base_url="http://127.0.0.1:9", network={"lan": True})
    out = send(http, r, effect="read")
    assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied"
    far = Provider(id="p", name="P", kind="reference", base_url="http://example.com")
    assert send(far, r, effect="read").error_class == "confinement_denied"


# 6: wall-clock deadline applies in reference sender too (dev), covered for confinement in test_confinement


# 7: one keying
def test_board_defs_and_envelope_use_same_unique_keys(store, send):
    from personal_world.worlds.cards import CardService, home_board_defs
    from personal_world.worlds.models import Board
    from personal_world.worlds.runner import Runner
    add_request(store, ttl_s=0)
    add_card(store, fields=[{"path": "$.a", "label": "Size"}, {"path": "$.b", "label": "size"}],
             meter={"type": "progress", "value": "cpu-load", "max": 1})
    store.save("board", Board(id="home", title="H", home=True, items=[{"card": "c1"}]))
    send.responses["/items"] = ok({"a": 1, "b": 2})
    keys = [f["key"] for f in home_board_defs(store)["items"][0]["fields"]]
    e = CardService(store, Runner(store, send)).build("c1")
    assert keys == ["size", "size-2"] and list(e["values"]) == keys
    assert "Size: 1" in e["meter"]["text_equivalent"] and "size: 2" in e["meter"]["text_equivalent"]


# 8: no absolute paths; userinfo rejected
def test_errors_use_relative_paths(tmp_path):
    base = tmp_path / "cfg" / "worlds" / "providers"
    base.mkdir(parents=True)
    (base / "bad.yaml").write_text("schema_version: 1\nid: bad\nname: [x\n")
    s = ConfigStore(tmp_path / "cfg")
    blob = json.dumps(s.errors())
    assert str(tmp_path) not in blob and "worlds/providers/bad.yaml" in blob


def test_base_url_userinfo_rejected():
    for bad in ("http://u:p@host", "http://u@host/x", "http://host/x?a=1", "http://host/x#f"):
        with pytest.raises(ValidationError):
            Provider(id="p", name="P", kind="http", base_url=bad)


def test_redirect_note_does_not_record_target():
    with ReferenceServer() as srv:
        p = Provider(id="ref", name="R", kind="reference", base_url=srv.base_url, network={"lan": True})
        r = Request(id="ref.t", provider="ref", path="/redirect")
        out = reference_send({})(p, r, effect="read")
        assert out.error_class == "redirect_refused" and "/items" not in out.note


# 9: etag changes when a file goes invalid; JSONPath validated at save
def test_etag_changes_when_file_goes_invalid(tmp_path):
    from personal_world.worlds.models import Provider as P
    s = ConfigStore(tmp_path)
    old = s.save("provider", P(id="ref", name="R", kind="reference", base_url="http://127.0.0.1:9"))
    f = tmp_path / "worlds" / "providers" / "ref.yaml"
    f.write_text("schema_version: 1\nid: ref\nname: [broken\n")
    s.reload()
    assert s.etag("provider", "ref") != old
    assert s.get("provider", "ref").name == "R"
    with pytest.raises(EtagMismatch):
        s.save("provider", P(id="ref", name="New", kind="reference", base_url="http://127.0.0.1:9"), etag=old)
    err = s.errors()[0]
    s.save("provider", P(id="ref", name="Fixed", kind="reference", base_url="http://127.0.0.1:9"), etag=err["etag"])
    assert s.get("provider", "ref").name == "Fixed" and not s.errors()


@pytest.mark.parametrize("bad", ["a.b", "$..a", "$.a[?(@.x)]", "$.a[1:2]"])
def test_jsonpaths_validated_at_save_time(bad):
    with pytest.raises(ValidationError):
        Card(id="c", title="t", request="ref.items", meaning={"concept": "c", "short": "s"},
             fields=[{"path": bad, "label": "L"}])
    with pytest.raises(ValidationError):
        Card(id="c", title="t", request="ref.items", meaning={"concept": "c", "short": "s"},
             status={"path": bad})
    with pytest.raises(ValidationError):
        Assertion(path=bad, exists=True)
