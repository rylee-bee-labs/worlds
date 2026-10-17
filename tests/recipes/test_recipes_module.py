"""The recipe loader and installer: placeholders are refused, secrets are names, existing config is kept."""
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from personal_world.worlds.config_store import ConfigStore
from personal_world.worlds.recipes import RecipeError, install, list_recipes, load_recipe


def make(root: Path, status="ready", base="http://thing.lan.example:1234"):
    d = root / "thing"
    (d / "requests").mkdir(parents=True)
    (d / "cards").mkdir()
    (d / "recipe.yaml").write_text(yaml.safe_dump({"schema_version": 1, "name": "thing", "title": "Thing", "summary": "A thing.", "status": status, "note": "waiting" if status == "planned" else "", "env": ["THING_API_KEY"]}))
    (d / "provider.yaml").write_text(yaml.safe_dump({"schema_version": 1, "id": "thing", "name": "Thing", "kind": "http", "base_url": base, "auth": {"type": "header", "header_name": "X-Api-Key", "secret_ref": "env:THING_API_KEY"}, "network": {"lan": True}}))
    (d / "requests" / "status.yaml").write_text(yaml.safe_dump({"schema_version": 1, "id": "thing.status", "provider": "thing", "path": "/status", "effect": "read"}))
    (d / "cards" / "thing.yaml").write_text(yaml.safe_dump({"schema_version": 1, "id": "thing", "title": "Thing", "request": "thing.status", "meaning": {"concept": "a thing", "short": "A thing"}}))
    return d


def test_list_and_load(tmp_path):
    make(tmp_path)
    assert [i.name for i in list_recipes(tmp_path)] == ["thing"]
    r = load_recipe("thing", tmp_path)
    assert r.provider and [c.id for c in r.cards] == ["thing"] and [q.id for q in r.requests] == ["thing.status"]


def test_install_refuses_the_placeholder_and_never_writes_it(tmp_path):
    make(tmp_path)
    store = ConfigStore(tmp_path / "cfg")
    with pytest.raises(RecipeError, match="--base-url"):
        install(store, load_recipe("thing", tmp_path))
    assert not (tmp_path / "cfg" / "worlds").exists() or not list((tmp_path / "cfg" / "worlds").rglob("*.yaml"))


def test_install_writes_the_real_address_and_secret_name_only(tmp_path):
    make(tmp_path)
    store = ConfigStore(tmp_path / "cfg")
    written = install(store, load_recipe("thing", tmp_path), base_url="http://thing.home.test:1234", secret_ref="env:MY_KEY")
    assert written == ["provider:thing", "request:thing.status", "card:thing"]
    p = store.get("provider", "thing")
    assert p.base_url == "http://thing.home.test:1234" and p.auth.secret_ref == "env:MY_KEY"
    text = (tmp_path / "cfg" / "worlds" / "providers" / "thing.yaml").read_text()
    assert "MY_KEY" in text and "secret" not in text.replace("secret_ref", "")


def test_install_keeps_existing_config_unless_overwrite(tmp_path):
    make(tmp_path)
    store = ConfigStore(tmp_path / "cfg")
    install(store, load_recipe("thing", tmp_path), base_url="http://thing.home.test:1234")
    assert install(store, load_recipe("thing", tmp_path), base_url="http://thing2.home.test:1234") == []
    assert store.get("provider", "thing").base_url == "http://thing.home.test:1234"
    assert "provider:thing" in install(store, load_recipe("thing", tmp_path), base_url="http://thing2.home.test:1234", overwrite=True)
    assert store.get("provider", "thing").base_url == "http://thing2.home.test:1234"


def test_a_planned_recipe_lists_but_does_not_install(tmp_path):
    make(tmp_path, status="planned")
    assert list_recipes(tmp_path)[0].status == "planned"
    with pytest.raises(RecipeError, match="waiting"):
        install(ConfigStore(tmp_path / "cfg"), load_recipe("thing", tmp_path), base_url="http://thing.home.test:1234")


def test_a_bad_secret_ref_or_name_is_refused(tmp_path):
    make(tmp_path)
    with pytest.raises(ValidationError):
        install(ConfigStore(tmp_path / "cfg"), load_recipe("thing", tmp_path), base_url="http://thing.home.test:1234", secret_ref="literal-key-value")
    with pytest.raises(RecipeError):
        load_recipe("../etc", tmp_path)
