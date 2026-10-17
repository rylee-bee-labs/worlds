"""Room recipes (``kind: room0``, ``status: room``) install through the loader: provider-only, no invented files.

Why a NEW file rather than ``tests/recipes/test_recipes_module.py``: that file documents the generic HTTP
recipe loader/installer, and no existing test may be edited; a separate file keeps the room-install evidence
together with the room recipe metadata without touching it. The recipe always comes from ``load_recipe`` /
``recipes_dir``, never a hand-built object, so this proves the install goes through the real loader path.
"""
from __future__ import annotations

import pytest

from personal_world.worlds.config_store import ConfigStore
from personal_world.worlds.models import Provider
from personal_world.worlds.recipes import RecipeError, install, load_recipe, recipes_dir

ROOM_RECIPES = ["project-home", "discovery-room"]
REAL_URL = "http://127.0.0.1:9"
OTHER_URL = "http://127.0.0.1:10"


@pytest.mark.parametrize("name", ROOM_RECIPES)
def test_room_recipe_install_routes_through_loader(tmp_path, name):
    # Load through the loader: a room recipe is valid and installable, not planned.
    recipe = load_recipe(name, recipes_dir())
    assert recipe.info.status == "room"
    assert recipe.provider is not None and recipe.provider.kind == "room0"
    assert not recipe.requests and not recipe.cards and not recipe.actions

    store = ConfigStore(tmp_path / "cfg")

    # No real address: the placeholder base_url is refused and nothing is ever written.
    with pytest.raises(RecipeError):
        install(store, recipe)
    assert store.get("provider", name) is None
    assert not (tmp_path / "cfg" / "worlds" / "providers").exists() or not list(
        (tmp_path / "cfg" / "worlds" / "providers").glob("*.yaml")
    )

    # With a real loopback address the provider goes in through the same ConfigStore path as any recipe.
    written = install(store, recipe, base_url=REAL_URL)
    assert written == [f"provider:{name}"]
    assert store.errors() == []
    provider = store.get("provider", name)
    assert isinstance(provider, Provider) and provider.kind == "room0"
    assert provider.base_url == REAL_URL

    # Provider only: a room maps its own cards through C8, so install invents no request/card/action files.
    snapshot = store.snapshot()
    assert snapshot["request"] == {} and snapshot["card"] == {} and snapshot["action"] == {}
    on_disk = {p.name for p in (tmp_path / "cfg" / "worlds" / "providers").glob("*.yaml")}
    assert on_disk == {f"{name}.yaml"}

    # A second install with a different address keeps the first (existing no-overwrite behaviour).
    assert install(store, recipe, base_url=OTHER_URL) == []
    assert store.get("provider", name).base_url == REAL_URL


@pytest.mark.parametrize("name", ROOM_RECIPES)
def test_room_recipe_keeps_principal_placeholder_and_secret_name_only(tmp_path, name):
    store = ConfigStore(tmp_path / "cfg")
    install(store, load_recipe(name, recipes_dir()), base_url=REAL_URL, secret_ref="env:MY_ROOM_TOKEN")
    provider = store.get("provider", name)
    # secret_ref overrides the placeholder name; the principal placeholder is installed as written (never
    # silently rewritten) and only the secret *name* is written, never a value.
    assert provider.auth.secret_ref == "env:MY_ROOM_TOKEN"
    assert provider.principal_id == "your-person-id"
    text = (tmp_path / "cfg" / "worlds" / "providers" / f"{name}.yaml").read_text()
    assert "MY_ROOM_TOKEN" in text
