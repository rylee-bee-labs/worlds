"""Acceptance tests for personal_world.worlds.config_store (C1 store behaviour)."""
import stat

import pytest
import yaml

from personal_world.worlds.config_store import ConfigInvalid, ConfigStore, EtagMismatch
from personal_world.worlds.models import Action, Board, Card, Provider, Request


def provider(**kw):
    d = dict(id="ref", name="Ref", kind="reference", base_url="http://127.0.0.1:9000")
    d.update(kw)
    return Provider(**d)


def request(**kw):
    d = dict(id="ref.items", provider="ref", path="/items")
    d.update(kw)
    return Request(**d)


def card(**kw):
    d = dict(id="items", title="Items", request="ref.items", meaning={"concept": "c", "short": "s"})
    d.update(kw)
    return Card(**d)


@pytest.fixture
def store(tmp_path):
    return ConfigStore(tmp_path)


def seed(store):
    store.save("provider", provider())
    store.save("request", request())
    store.save("card", card())
    store.save("board", Board(id="home", title="Home", home=True, items=[{"card": "items"}]))
    store.save("action", Action(id="go", request="ref.items", name="Go"))


def test_layout_and_schema_version(store, tmp_path):
    seed(store)
    base = tmp_path / "worlds"
    assert (base / "providers" / "ref.yaml").is_file()
    assert (base / "requests" / "ref" / "ref.items.yaml").is_file()
    assert (base / "cards" / "items.yaml").is_file()
    assert (base / "boards" / "home.yaml").is_file()
    assert (base / "actions" / "go.yaml").is_file()
    for p in base.rglob("*.yaml"):
        assert yaml.safe_load(p.read_text())["schema_version"] == 1


def test_round_trip_load_save_load_equal(store, tmp_path):
    seed(store)
    first = ConfigStore(tmp_path).snapshot()
    s2 = ConfigStore(tmp_path)
    for kind, obj in s2.iter_all():
        s2.save(kind, obj)
    assert ConfigStore(tmp_path).snapshot() == first


def test_atomic_write_leaves_no_tmp_and_is_0600_or_0644_not_world_writable(store, tmp_path):
    seed(store)
    assert not list((tmp_path / "worlds").rglob("*.tmp*"))
    for p in (tmp_path / "worlds").rglob("*.yaml"):
        assert not stat.S_IMODE(p.stat().st_mode) & stat.S_IWOTH


def test_etag_conflict_409(store):
    etag = store.save("provider", provider())
    etag2 = store.save("provider", provider(name="Renamed"), etag=etag)
    assert etag2 != etag
    with pytest.raises(EtagMismatch):
        store.save("provider", provider(name="Stale"), etag=etag)
    assert store.get("provider", "ref").name == "Renamed"
    assert store.etag("provider", "ref") == etag2


def test_create_with_etag_of_existing_conflicts(store):
    store.save("provider", provider())
    with pytest.raises(EtagMismatch):
        store.save("provider", provider(), etag="")  # "" = "must not exist yet"


def test_dangling_references_rejected(store):
    with pytest.raises(ConfigInvalid):
        store.save("request", request())  # provider missing
    store.save("provider", provider())
    with pytest.raises(ConfigInvalid):
        store.save("card", card())  # request missing
    store.save("request", request())
    with pytest.raises(ConfigInvalid):
        store.save("board", Board(id="home", title="H", items=[{"card": "nope"}]))
    with pytest.raises(ConfigInvalid):
        store.save("action", Action(id="go", request="ref.nope", name="Go"))


def test_secret_ref_validated_but_value_never_stored(store, tmp_path):
    store.save("provider", provider(auth={"type": "bearer", "secret_ref": "env:REF_TOKEN"}))
    text = (tmp_path / "worlds" / "providers" / "ref.yaml").read_text()
    assert "env:REF_TOKEN" in text


def test_invalid_hand_edit_keeps_last_valid_active(store, tmp_path):
    seed(store)
    f = tmp_path / "worlds" / "providers" / "ref.yaml"
    f.write_text("schema_version: 1\nid: ref\nname: [broken\n")
    store.reload()
    assert store.get("provider", "ref").name == "Ref"  # last valid stays
    errs = store.errors()
    assert any("ref" in e["path"] for e in errs)
    assert "Traceback" not in repr(errs)


def test_invalid_file_on_cold_start_is_reported_not_loaded(tmp_path):
    base = tmp_path / "worlds" / "providers"
    base.mkdir(parents=True)
    (base / "bad.yaml").write_text("schema_version: 1\nid: bad\nname: x\nkind: nope\nbase_url: x\n")
    s = ConfigStore(tmp_path)
    assert s.get("provider", "bad") is None
    assert s.errors()


def test_filename_must_match_id(tmp_path):
    base = tmp_path / "worlds" / "providers"
    base.mkdir(parents=True)
    (base / "other.yaml").write_text(
        "schema_version: 1\nid: ref\nname: R\nkind: reference\nbase_url: http://127.0.0.1:1\n"
    )
    s = ConfigStore(tmp_path)
    assert s.get("provider", "ref") is None and s.errors()


def test_unknown_schema_version_rejected(tmp_path):
    base = tmp_path / "worlds" / "providers"
    base.mkdir(parents=True)
    (base / "ref.yaml").write_text(
        "schema_version: 2\nid: ref\nname: R\nkind: reference\nbase_url: http://127.0.0.1:1\n"
    )
    assert ConfigStore(tmp_path).errors()


def test_traversal_ids_rejected(store):
    evil = Provider.model_construct(schema_version=1, id="../evil", name="x", kind="http", base_url="http://x")
    with pytest.raises(ConfigInvalid):
        store.save("provider", evil)


def test_delete_blocked_while_referenced(store):
    seed(store)
    with pytest.raises(ConfigInvalid):
        store.delete("provider", "ref")
    store.delete("action", "go")
    store.delete("board", "home")
    store.delete("card", "items")
    store.delete("request", "ref.items")
    store.delete("provider", "ref")
    assert store.get("provider", "ref") is None


def test_reload_never_executes_anything(store, monkeypatch):
    seed(store)
    import personal_world.worlds.confinement as c
    called = []
    monkeypatch.setattr(c, "confined_request", lambda *a, **k: called.append(1))
    store.reload()
    assert not called


def test_action_version_changes_when_provider_destination_changes(store):
    seed(store)
    v1 = store.action_version("go")
    store.save("provider", provider(base_url="http://127.0.0.1:9100"), etag=store.etag("provider", "ref"))
    assert store.action_version("go") != v1


def test_change_listener_reports_changed_action_versions(store):
    seed(store)
    seen = []
    store.on_change(lambda ids: seen.append(set(ids)))
    store.save("request", request(path="/items2"), etag=store.etag("request", "ref.items"))
    assert seen and "go" in seen[-1]
