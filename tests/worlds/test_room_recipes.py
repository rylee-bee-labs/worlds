"""The shipped room recipes are valid, placeholder-only templates (in the recipe-directory format)."""
from pathlib import Path

import pytest

from personal_world.worlds.recipes import load_recipe

RECIPES = Path(__file__).resolve().parents[2] / "config" / "recipes"


@pytest.mark.parametrize("name", ["discovery-room", "project-home"])
def test_room_recipe_loads_and_holds_only_placeholders(name):
    r = load_recipe(name, RECIPES)
    p = r.provider
    assert p.kind == "room0" and p.auth.secret_ref.startswith("env:") and p.principal_id == "your-person-id"
    assert p.base_url.endswith(".lan.example") and p.public_url.endswith(".lan.example")
    assert r.info.env == [p.auth.secret_ref.split(":", 1)[1]]
    text = (RECIPES / name / "provider.yaml").read_text() + (RECIPES / name / "recipe.yaml").read_text()
    for secretish in ("Bearer ", "password", "api_key"):
        assert secretish not in text


def test_the_two_recipes_state_their_governance():
    c = load_recipe("discovery-room", RECIPES).provider
    ph = load_recipe("project-home", RECIPES).provider
    assert c.governed_by_project_home() is False and c.group == "life"
    assert ph.governed_by_project_home() is True and ph.group == "machine"
