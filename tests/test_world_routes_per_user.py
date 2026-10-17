"""World-touching routes follow the caller's own world and journal.

In multi mode /api/daily, /api/memory/search, /api/exports/world,
/api/backup and /api/world/{intent,fact,policy} read and write the
caller's tree under data/users/<id>/. Instance-level routes (status,
manifest, connections, ...) stay instance-wide. Single mode keeps the
legacy instance paths.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "instancetoken"  # pw-safety: synthetic
OWNER = {"Authorization": f"Bearer {TOKEN}"}


def _app(tmp_path, monkeypatch, mode):
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    return TestClient(create_app(tmp_path, tmp_path))


def _second_person(c):
    r = c.post(
        "/api/identity/users",
        json={"user_id": "beta", "display_name": "Made up person"},
        headers=OWNER,
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


def _without_observed(payload):
    """Drop generated last_observed timestamps (any depth) from a payload.

    status_map() stamps a fresh wall-clock value per request, so two calls
    a second apart differ only there. Everything else must still match."""
    if isinstance(payload, dict):
        return {k: _without_observed(v) for k, v in payload.items() if k != "last_observed"}
    if isinstance(payload, list):
        return [_without_observed(v) for v in payload]
    return payload


def test_multi_world_writes_land_in_the_callers_tree_and_stay_private(tmp_path, monkeypatch):
    c = _app(tmp_path, monkeypatch, "multi")
    beta = _second_person(c)
    assert c.post("/api/world/fact", json={"key": "owner_note", "value": "x"}, headers=OWNER).status_code == 200
    assert c.post("/api/world/intent", json={"key": "owner_goal", "value": "y"}, headers=OWNER).status_code == 200
    assert c.post("/api/world/policy", json={"key": "owner_rule", "effect": "deny"}, headers=OWNER).status_code == 200
    owner_world = json.loads((tmp_path / "users" / "primary" / "world.json").read_text())
    assert "owner_note" in json.dumps(owner_world) and "owner_goal" in json.dumps(owner_world)
    assert not (tmp_path / "world.json").exists() or "owner_note" not in (tmp_path / "world.json").read_text()

    for path in ("/api/exports/world", "/api/backup"):
        mine = c.get(path, headers=OWNER).text
        theirs = c.get(path, headers=beta).text
        assert "owner_goal" in mine or "owner_note" in mine, path
        assert "owner_note" not in theirs and "owner_goal" not in theirs and "owner_rule" not in theirs, path


def test_multi_daily_run_saves_the_callers_world_not_the_instance_one(tmp_path, monkeypatch):
    c = _app(tmp_path, monkeypatch, "multi")
    beta = _second_person(c)
    assert c.post("/api/daily", headers=beta).status_code == 200
    assert (tmp_path / "users" / "beta" / "world.json").exists()
    assert not (tmp_path / "users" / "primary" / "world.json").exists()
    assert c.get("/api/daily", headers=beta).status_code == 200


def test_multi_memory_search_answers_from_the_callers_registry(tmp_path, monkeypatch):
    c = _app(tmp_path, monkeypatch, "multi")
    beta = _second_person(c)
    assert c.get("/api/memory/search", params={"q": "anything"}, headers=beta).status_code == 200


def test_instance_level_routes_stay_instance_wide(tmp_path, monkeypatch):
    c = _app(tmp_path, monkeypatch, "multi")
    beta = _second_person(c)
    c.post("/api/world/fact", json={"key": "owner_note", "value": "x"}, headers=OWNER)
    for path in ("/api/status", "/api/manifest", "/api/connections/overview", "/api/exports/settings", "/api/templates"):
        a = c.get(path, headers=OWNER)
        b = c.get(path, headers=beta)
        assert a.status_code == 200 and b.status_code == 200, path
        assert _without_observed(a.json()) == _without_observed(b.json()), path


def test_without_observed_ignores_only_the_timestamp():
    # Differing only in last_observed, at two different depths (dict and
    # list element), compares equal.
    left = {"a": {"last_observed": 1}, "b": [{"last_observed": 2, "x": 3}]}
    right = {"a": {"last_observed": 9}, "b": [{"last_observed": 8, "x": 3}]}
    assert _without_observed(left) == _without_observed(right)
    # A non-timestamp difference is still caught.
    assert _without_observed({"a": {"last_observed": 1, "x": 2}}) != _without_observed(
        {"a": {"last_observed": 9, "x": 3}}
    )
    # Sibling keys are kept and the input is not mutated.
    payload = {"a": {"last_observed": 1, "x": 2}, "c": 4}
    assert _without_observed(payload) == {"a": {"x": 2}, "c": 4}
    assert payload == {"a": {"last_observed": 1, "x": 2}, "c": 4}


def test_single_mode_keeps_the_legacy_instance_world(tmp_path, monkeypatch):
    c = _app(tmp_path, monkeypatch, "single")
    assert c.post("/api/world/fact", json={"key": "legacy_note", "value": "x"}, headers=OWNER).status_code == 200
    assert "legacy_note" in (tmp_path / "world.json").read_text()
    assert "legacy_note" in c.get("/api/backup", headers=OWNER).text
    assert not (tmp_path / "users").exists() or not any((tmp_path / "users").glob("*/world.json"))
