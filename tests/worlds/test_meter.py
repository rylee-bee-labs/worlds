"""C1/C2 meter: the card names its sources, the envelope carries resolved numbers (missing is omitted)."""
import pytest
from pydantic import ValidationError

from personal_world.worlds.cards import CardService
from personal_world.worlds.models import Meter
from personal_world.worlds.runner import Runner

from .conftest import add_card, add_request, ok

F = [{"path": "$.cpu", "label": "CPU", "format": "percent"}, {"path": "$.used", "label": "Used", "format": "bytes"}]


def build(store, send, meter, body, fields=F):
    add_request(store, ttl_s=0)
    add_card(store, fields=fields, meter=meter)
    send.responses["/items"] = ok(body)
    return CardService(store, Runner(store, send)).build("c1")["meter"]


def test_progress_from_field_key_and_literal_max(store, send):
    m = build(store, send, {"type": "progress", "value": "cpu", "max": 1.0}, {"cpu": 0.25, "used": 5})
    assert m["type"] == "progress" and m["value"] == 0.25 and m["max"] == 1.0 and "CPU: 25%" in m["text_equivalent"]


def test_progress_from_paths(store, send):
    m = build(store, send, {"type": "progress", "value": "$.disk.used", "max": "$.disk.total"},
              {"cpu": 1, "used": 1, "disk": {"used": 512, "total": 1024}})
    assert (m["value"], m["max"]) == (512, 1024)


def test_zero_is_a_real_value_but_missing_is_omitted(store, send):
    m = build(store, send, {"type": "progress", "value": "cpu", "max": "$.total"}, {"cpu": 0, "used": 1})
    assert m["value"] == 0 and "max" not in m                       # missing max omitted, explicit 0 kept
    m = build(store, send, {"type": "progress", "value": "cpu"}, {"used": 1})
    assert "value" not in m and "max" not in m and m["type"] == "progress"


@pytest.mark.parametrize("bad", [True, "text", None, [1], {"a": 1}, float("inf")])
def test_non_numbers_are_omitted(store, send, bad):
    m = build(store, send, {"type": "progress", "value": "$.cpu"}, {"cpu": bad, "used": 1})
    assert "value" not in m


def test_segments_count_and_filled(store, send):
    m = build(store, send, {"type": "segments", "count": 5, "filled": "$.done"}, {"done": 3, "cpu": 0, "used": 0})
    assert m["count"] == 5 and m["filled"] == 3
    m = build(store, send, {"type": "segments", "count": "$.n", "filled": "$.done"}, {"cpu": 0, "used": 0})
    assert "count" not in m and "filled" not in m


def test_items_for_list_meters(store, send):
    m = build(store, send, {"type": "dots", "items": "$.days[*]"}, {"days": [1, 0, 1, "x", True, None, {"a": 1}], "cpu": 0, "used": 0})
    assert m["items"] == [1, 0, 1, "x", True]                      # only numbers, strings, bools
    m = build(store, send, {"type": "dots", "items": "$.days[*]"}, {"days": [], "cpu": 0, "used": 0})
    assert m["items"] == []                                        # an existing empty list is real
    m = build(store, send, {"type": "dots", "items": "$.nothing[*]"}, {"cpu": 0, "used": 0})
    assert "items" not in m
    big = build(store, send, {"type": "bars", "items": "$.v[*]"}, {"v": list(range(500)), "cpu": 0, "used": 0})
    assert len(big["items"]) == 200


def test_no_meter_is_none_and_stale_uses_last_good(store, send):
    add_request(store, ttl_s=0)
    add_card(store, fields=F, meter={"type": "progress", "value": "cpu", "max": 1})
    send.responses["/items"] = ok({"cpu": 0.5, "used": 1})
    svc = CardService(store, Runner(store, send))
    assert svc.build("c1")["meter"]["value"] == 0.5
    from personal_world.worlds.confinement import RawResponse
    send.responses["/items"] = RawResponse(503)
    e = svc.build("c1")
    assert e["freshness"] == "stale" and e["meter"]["value"] == 0.5
    add_card(store, "c2", fields=F)
    assert svc.build("c2")["meter"] is None


def test_unknown_when_not_configured_omits_numbers(store, send):
    add_request(store, ttl_s=0)
    add_card(store, fields=F, meter={"type": "progress", "value": "cpu", "max": 1})
    import os
    os.remove(next((store._worlds / "requests").rglob("ref.items.yaml")))
    store.reload()
    m = CardService(store, Runner(store, send)).build("c1")["meter"]
    assert "value" not in m and m["max"] == 1                       # a configured literal is not data


@pytest.mark.parametrize("meter", [
    {"type": "progress"}, {"type": "segments", "count": 3}, {"type": "segments", "filled": 1},
    {"type": "progress", "value": 5}, {"type": "progress", "value": "$..x"}, {"type": "progress", "value": "Bad Key"},
    {"type": "progress", "value": "cpu", "max": True}, {"type": "dots", "items": "cpu"},
    {"type": "dots", "items": "$.a[?(@.b)]"}, {"type": "progress", "value": "cpu", "unknown": 1}])
def test_meter_config_validated(meter):
    with pytest.raises(ValidationError):
        Meter(**meter)


def test_seeded_reference_status_has_a_real_progress_meter(store, send):
    from personal_world.worlds.reference_provider import ReferenceServer, reference_send
    from personal_world.worlds.seed import seed_reference_config
    with ReferenceServer() as srv:
        seed_reference_config(store, srv.base_url)
        m = CardService(store, Runner(store, reference_send({"REF_TOKEN": "x"}))).build("reference-status")["meter"]
    assert m["type"] == "progress" and m["value"] == 0.256 and m["max"] == 1.0
