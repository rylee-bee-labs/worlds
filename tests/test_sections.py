"""P1 T1: section registry + per-person layout (docs/p1/FOUNDATION-SPEC.md §2).

- registry defaults are tracked code; the owner's order/hidden live in
  their own world.json (world-classified, never settings-export)
- only `settings` is pinned; `today` is hideable like any other section
- status comes from status.py's closed vocabulary or is null; a missing
  or failing provider never removes a section
- PUT is step-up gated, persons only, validation errors are collected
- GET /api/prefs/schema mirrors prefs.PREFS so Settings can't offer a
  value the server rejects
"""
import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world import export, prefs, sections  # noqa: E402
from personal_world.app import load_world, save_world  # noqa: E402
from personal_world.world import World  # noqa: E402

REPO = Path(__file__).parent.parent
MANIFEST = REPO / "design" / "assets" / "icons" / "manifest.json"

AUTH = {"Authorization": "Bearer instancetoken"}
STEP = {**AUTH, "X-PW-StepUp": "1"}
DEFAULT_ORDER = ["today", "media", "projects", "lab",
                 "journal", "vault", "chat", "settings"]


def _make(tmp_path, monkeypatch, mode="single"):
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    if not (tmp_path / "world.json").exists():
        init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    return TestClient(create_app(tmp_path, tmp_path))


@pytest.fixture
def env(tmp_path, monkeypatch):
    return _make(tmp_path, monkeypatch), tmp_path


def _sections(c, headers=AUTH):
    r = c.get("/api/sections", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["schema"] == sections.SCHEMA
    return body["data"]["sections"]


def _by_id(items):
    return {s["id"]: s for s in items}


# --- defaults --------------------------------------------------------

def test_default_get_returns_registry_in_default_order(env):
    c, _ = env
    items = _sections(c)
    assert [s["id"] for s in items] == DEFAULT_ORDER
    assert [s["order"] for s in items] == list(range(8))
    by = _by_id(items)
    assert by["settings"]["pinned"] is True
    assert all(s["pinned"] is False for s in items if s["id"] != "settings")
    assert all(s["visible"] is True for s in items)
    assert by["chat"]["kind"] == "transitional"
    assert set(items[0]) == {"id", "label", "icon", "order", "visible",
                             "pinned", "kind", "configured", "status"}


def test_today_has_null_status_and_is_configured(env):
    c, _ = env
    today = _by_id(_sections(c))["today"]
    assert today["status"] is None
    assert today["configured"] is True


def test_media_zero_provider_is_not_configured_but_present(env):
    c, _ = env
    media = _by_id(_sections(c))["media"]
    assert media["status"] == "not_configured"
    assert media["configured"] is False
    assert media["visible"] is True


def test_resolve_status_configured_matrix():
    fake = {
        "media": {"status": "disabled"},
        "source_control": {"status": "healthy"},
    }
    by = _by_id(sections.resolve_sections(None, fake))
    assert by["media"]["status"] == "disabled"
    assert by["media"]["configured"] is False
    assert by["projects"]["status"] == "healthy"
    assert by["projects"]["configured"] is True
    # missing capability -> not_configured, never an invented value
    assert by["lab"]["status"] == "not_configured"
    assert by["lab"]["configured"] is False
    assert by["today"]["status"] is None
    from personal_world.status import RANK
    for s in by.values():
        assert s["status"] is None or s["status"] in RANK


# --- PUT -------------------------------------------------------------

def test_put_order_reorders_and_persists(env, monkeypatch):
    c, tmp = env
    new_order = ["settings", "chat", "today"]
    r = c.put("/api/sections", json={"order": new_order}, headers=STEP)
    assert r.status_code == 200, r.text
    got = [s["id"] for s in r.json()["data"]["sections"]]
    assert got[:3] == new_order
    assert got == new_order + [i for i in DEFAULT_ORDER if i not in new_order]
    assert [s["id"] for s in _sections(c)] == got
    # stored in the caller's world.json, not anywhere tracked
    payload = json.loads((tmp / "world.json").read_text())
    assert payload["layout"]["sections"]["order"] == new_order
    assert payload["layout"]["sections"]["schema"] == sections.SCHEMA
    # a fresh app over the same data dir sees the same layout
    c2 = _make(tmp, monkeypatch)
    assert [s["id"] for s in _sections(c2)] == got


def test_put_hidden_today_is_allowed(env):
    c, _ = env
    r = c.put("/api/sections", json={"hidden": ["today"]}, headers=STEP)
    assert r.status_code == 200, r.text
    by = _by_id(r.json()["data"]["sections"])
    assert by["today"]["visible"] is False
    assert "today" in by  # hidden != removed
    assert _by_id(_sections(c))["today"]["visible"] is False


def test_put_hidden_settings_is_rejected_as_pinned(env):
    c, _ = env
    r = c.put("/api/sections", json={"hidden": ["settings"]}, headers=STEP)
    assert r.status_code == 400
    assert "pinned" in r.json()["detail"]
    assert _by_id(_sections(c))["settings"]["visible"] is True


def test_put_collects_unknown_and_duplicate_errors(env):
    c, _ = env
    r = c.put("/api/sections", json={"order": ["nope"]}, headers=STEP)
    assert r.status_code == 400 and "unknown" in r.json()["detail"]
    r = c.put("/api/sections", json={"order": ["today", "today"]},
              headers=STEP)
    assert r.status_code == 400 and "duplicate" in r.json()["detail"]
    r = c.put("/api/sections",
              json={"order": ["today", "today", "nope"],
                    "hidden": ["settings", "zzz"]},
              headers=STEP)
    assert r.status_code == 400
    detail = r.json()["detail"]
    for word in ("unknown", "duplicate", "pinned", "zzz", "nope"):
        assert word in detail
    # non-list values are a validation error, not a crash
    r = c.put("/api/sections", json={"order": "today"}, headers=STEP)
    assert r.status_code == 400 and "list" in r.json()["detail"]
    assert c.put("/api/sections", json=[1, 2], headers=STEP).status_code == 400
    assert c.put("/api/sections", content=b"not json",
                 headers={**STEP, "content-type": "application/json"},
                 ).status_code == 400
    # nothing partial was applied
    assert [s["id"] for s in _sections(c)] == DEFAULT_ORDER


def test_put_partial_keeps_other_key(env):
    c, _ = env
    assert c.put("/api/sections", json={"hidden": ["media"]},
                 headers=STEP).status_code == 200
    r = c.put("/api/sections", json={"order": ["vault", "today"]},
              headers=STEP)
    assert r.status_code == 200
    items = r.json()["data"]["sections"]
    assert [s["id"] for s in items][:2] == ["vault", "today"]
    assert _by_id(items)["media"]["visible"] is False  # hidden kept
    r = c.put("/api/sections", json={"hidden": []}, headers=STEP)
    items = r.json()["data"]["sections"]
    assert [s["id"] for s in items][:2] == ["vault", "today"]  # order kept
    assert _by_id(items)["media"]["visible"] is True


def test_put_empty_lists_resets_to_defaults(env):
    c, _ = env
    c.put("/api/sections", json={"order": ["chat"], "hidden": ["media"]},
          headers=STEP)
    r = c.put("/api/sections", json={"order": [], "hidden": []},
              headers=STEP)
    assert r.status_code == 200
    items = r.json()["data"]["sections"]
    assert [s["id"] for s in items] == DEFAULT_ORDER
    assert all(s["visible"] for s in items)


def test_route_gates_are_declared(env):
    c, _ = env
    gates = {}
    for route in c.app.routes:
        if getattr(route, "path", None) == "/api/sections":
            for m in route.methods:
                gates[m] = [d.dependency.__name__
                            for d in route.dependencies]
    assert "require_step_up" in gates["PUT"]
    assert "require_auth" in gates["GET"]
    assert "require_step_up" not in gates["GET"]
    # and unauthenticated calls are refused
    assert c.get("/api/sections").status_code == 401
    assert c.put("/api/sections", json={}).status_code == 401


def test_put_journals_settings_change(env):
    c, tmp = env
    c.put("/api/sections", json={"order": ["chat"]}, headers=STEP)
    lines = (tmp / "journal.ndjson").read_text().splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    hits = [e for e in events
            if e["kind"] == "settings_change"
            and e["summary"] == "sections layout updated"]
    assert hits, events


# --- principals ------------------------------------------------------

def test_agent_principal_is_refused(tmp_path, monkeypatch):
    c = _make(tmp_path, monkeypatch, mode="multi")
    r = c.post("/api/identity/agents",
               json={"agent_id": "bot", "scopes": ["read", "write"]},
               headers=STEP)
    assert r.status_code == 200, r.text
    bot = {"Authorization": f"Bearer {r.json()['data']['token']}",
           "X-PW-StepUp": "1"}
    assert c.get("/api/sections", headers=bot).status_code == 403
    assert c.put("/api/sections", json={"hidden": ["today"]},
                 headers=bot).status_code == 403


def test_multi_mode_layouts_are_per_person(tmp_path, monkeypatch):
    c = _make(tmp_path, monkeypatch, mode="multi")
    r = c.post("/api/identity/users",
               json={"user_id": "second", "display_name": "Second"},
               headers=STEP)
    assert r.status_code == 200, r.text
    b = {"Authorization": f"Bearer {r.json()['data']['token']}"}
    b_step = {**b, "X-PW-StepUp": "1"}
    # A hides media
    assert c.put("/api/sections", json={"hidden": ["media"]},
                 headers=STEP).status_code == 200
    assert _by_id(_sections(c, AUTH))["media"]["visible"] is False
    assert _by_id(_sections(c, b))["media"]["visible"] is True
    # B reorders; A is unaffected
    assert c.put("/api/sections", json={"order": ["settings"]},
                 headers=b_step).status_code == 200
    assert [s["id"] for s in _sections(c, b)][0] == "settings"
    assert [s["id"] for s in _sections(c, AUTH)] == DEFAULT_ORDER
    # stored in each person's own tree
    assert (tmp_path / "users" / "second" / "world.json").exists()
    a_payload = json.loads((tmp_path / "users" / "primary" / "world.json").read_text())
    assert a_payload["layout"]["sections"]["hidden"] == ["media"]
    # the change event lands in each person's OWN journal, not the shared one
    b_journal = (tmp_path / "users" / "second" / "journal.ndjson").read_text()
    a_journal = (tmp_path / "users" / "primary" / "journal.ndjson").read_text()
    assert "sections layout updated" in b_journal
    assert "sections layout updated" in a_journal
    shared = tmp_path / "journal.ndjson"
    assert not shared.exists() or "sections layout updated" not in shared.read_text()


# --- registry / icons ------------------------------------------------

def test_registry_shape_and_icons_exist_in_manifest():
    ids = sections.manifest_icon_ids(MANIFEST)
    assert ids, "manifest yielded no icon ids"
    for spec in sections.SECTIONS:
        assert spec.icon in ids, f"{spec.id}: {spec.icon} not in manifest"
    assert [s.id for s in sections.SECTIONS] == DEFAULT_ORDER
    assert [s.default_order for s in sections.SECTIONS] == list(range(8))
    assert {s.id for s in sections.SECTIONS if s.pinned} == {"settings"}
    assert all(s.default_visible for s in sections.SECTIONS)
    # substitutions are recorded and are what the registry actually uses
    for sid, icon in sections.ICON_SUBSTITUTIONS.items():
        assert sections.BY_ID[sid].icon == icon
        assert icon in ids
    with pytest.raises(FrozenInstanceError):
        sections.SECTIONS[0].icon = "x"  # frozen


# --- prefs schema ----------------------------------------------------

def test_prefs_schema_mirrors_prefs_module(env):
    c, _ = env
    r = c.get("/api/prefs/schema", headers=AUTH)
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data) == set(prefs.PREFS)
    for key, spec in prefs.PREFS.items():
        entry = data[key]
        assert {"type", "default", "floor", "allowed"} <= set(entry)
        assert entry["default"] == spec.default
        assert entry["floor"] == spec.floor
        if isinstance(spec, prefs.NumberPref):
            assert entry["type"] == "number"
            assert entry["integer"] == spec.integer
            assert entry["unit"] == spec.unit
        elif isinstance(spec, prefs.CompanionIdPref):
            # The one row with no closed vocabulary: the allowed values are
            # the caller's own crew, so the row says so instead of listing a
            # list it cannot know (companions addendum item 4).
            assert entry["type"] == "companion_id"
            assert entry["allowed"] is None
            assert "crew" in entry["note"]
        else:
            assert entry["type"] == "enum"
    assert tuple(data["motion"]["allowed"]) == prefs.MOTION.allowed
    assert data["target_size"]["allowed"] == [44, 56]
    assert c.get("/api/prefs/schema").status_code == 401


# --- classification / persistence -----------------------------------

def test_layout_is_world_export_only():
    w = World()
    w.layout["sections"] = {"schema": sections.SCHEMA,
                            "order": ["chat"], "hidden": ["media"]}
    we = export.world_export(w)
    assert we["layout"]["sections"]["order"] == ["chat"]
    assert we["layout"] is not w.layout  # copy, not the live dict
    se = export.settings_export(w)
    assert "layout" not in se
    assert "layout" not in json.dumps(se)


def test_load_world_without_layout_is_backwards_compatible(tmp_path):
    from personal_world.model import SCHEMA_VERSION
    path = tmp_path / "world.json"
    path.write_text(json.dumps({"schema_version": SCHEMA_VERSION,
                                "facts": {}, "accessibility": {}}))
    w = load_world(path)
    assert w.layout == {}
    assert World().layout == {}
    # round trip keeps it under the unchanged schema version
    w.layout["sections"] = {"schema": sections.SCHEMA,
                            "order": [], "hidden": ["today"]}
    save_world(w, path)
    payload = json.loads(path.read_text())
    assert payload["schema_version"] == SCHEMA_VERSION
    assert load_world(path).layout == w.layout


def test_resolve_drops_unknown_and_pinned_hidden_from_stored_layout():
    stored = {"schema": sections.SCHEMA,
              "order": ["ghost", "vault", "vault", "today"],
              "hidden": ["settings", "ghost", "lab"]}
    items = sections.resolve_sections(stored, {})
    ids = [s["id"] for s in items]
    assert ids[:2] == ["vault", "today"]
    assert sorted(ids) == sorted(DEFAULT_ORDER)
    by = _by_id(items)
    assert by["settings"]["visible"] is True
    assert by["lab"]["visible"] is False
    assert [s["order"] for s in items] == list(range(8))
