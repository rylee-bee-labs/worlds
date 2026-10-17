"""Every shipped recipe (config/recipes/*): C1-valid, read-only, sanitized, and its cards map real-shaped sample responses.

No live calls: responses come from tests/recipes/samples/<recipe>.yaml (recorded shapes, sanitized).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

from personal_world.framework import validate_recipes
from personal_world.worlds.cards import CardService
from personal_world.worlds.config_store import ConfigStore
from personal_world.worlds.confinement import ConfinementError, RawResponse
from personal_world.worlds.recipes import (
    PUBLIC_READ_ONLY_HOSTS,
    install,
    is_public_read_only,
    list_recipes,
    load_recipe,
    recipes_dir,
)
from personal_world.worlds.runner import Runner

ROOT = Path(__file__).resolve().parents[2]
RECIPES = ROOT / "config" / "recipes"
SAMPLES = Path(__file__).parent / "samples"
READY = [i.name for i in list_recipes(RECIPES) if i.status == "ready"]
PLANNED = [i for i in list_recipes(RECIPES) if i.status == "planned"]
ALL_NAMES = [i.name for i in list_recipes(RECIPES)]
CARD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def test_recipes_dir_resolves_to_the_repo_copy():
    assert recipes_dir().resolve() == RECIPES.resolve()


class SampleSend:
    """A sender that answers each request id from the case's recorded responses."""

    def __init__(self, responses: dict[str, object]):
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, provider, request, *, effect):
        self.calls.append(request.id)
        assert effect == "read", f"{request.id} ran as {effect}; recipes only read"
        name = request.id.partition(".")[2]
        item = self.responses.get(name)
        if item is None:
            return ConfinementError("connection", "no sample for this request")
        if isinstance(item, dict) and "__error" in item:
            return ConfinementError(item["__error"], "sample failure")
        if isinstance(item, dict) and "__status" in item:
            return RawResponse(status_code=item["__status"], headers={"content-type": "application/json"}, body=b"{}", duration_ms=5)
        return RawResponse(status_code=200, headers={"content-type": "application/json"}, body=json.dumps(item).encode(), duration_ms=5)


def _load_cases(name: str) -> dict[str, list[dict]]:
    f = SAMPLES / f"{name}.yaml"
    assert f.is_file(), f"recipes/{name} has no samples file tests/recipes/samples/{name}.yaml"
    data = yaml.safe_load(f.read_text())
    return data["cards"]


def _installed(tmp_path, name):
    store = ConfigStore(tmp_path / "cfg")
    recipe = load_recipe(name, RECIPES)
    install(store, recipe, base_url="http://127.0.0.1:9")
    return store, recipe


@pytest.mark.parametrize("name", READY)
def test_recipe_installs_and_is_read_only(tmp_path, name):
    store, recipe = _installed(tmp_path, name)
    assert store.errors() == []
    action_requests = {a.request for a in recipe.actions}
    for r in recipe.requests:
        if r.id in action_requests:
            assert r.resolved_effect() == "write", f"{r.id} is an action's request and must declare effect: write"
        else:
            assert r.method in ("GET", "HEAD") and r.effect == "read", f"{r.id} must be a read (effect: read)"
            assert r.resolved_effect() == "read"
    for a in recipe.actions:
        assert a.approval == "always" and a.exposed is False, f"action {a.id}: approval always and exposed false until the owner enables it"
        assert a.access == "write"


@pytest.mark.parametrize("name", ALL_NAMES)
def test_every_recipe_says_whether_it_is_verified(name):
    text = (RECIPES / name / "recipe.yaml").read_text()
    assert re.search(r"^verified: (true|false)$", text, re.M), f"{name}: recipe.yaml must state verified: true|false (false until checked against a live service)"
    assert load_recipe(name, RECIPES).info.verified is False, f"{name}: only a live read-only check may set verified: true"


@pytest.mark.parametrize("name", READY)
def test_provider_is_a_sanitized_lan_template(name):
    recipe = load_recipe(name, RECIPES)
    p = recipe.provider
    assert p is not None and p.kind == "http"
    if not p.network.lan:
        # The narrow internet exception: https, allowlisted host, no auth, reads only, no actions.
        assert is_public_read_only(recipe), f"{name}: an internet provider must be https, allowlisted, no auth, read-only"
        assert urlsplit(p.base_url).hostname in PUBLIC_READ_ONLY_HOSTS, p.base_url
        return
    assert re.match(r"^https?://[a-z0-9-]+\.lan\.example(:\d+)?$", p.base_url), p.base_url
    if p.auth.type != "none":
        assert p.auth.secret_ref and p.auth.secret_ref.startswith("env:")
        env = p.auth.secret_ref.removeprefix("env:")
        assert ENV_NAME_RE.match(env) and env in recipe.info.env, f"{env} must be listed in recipe.yaml env"
    assert p.tls_verify is True


@pytest.mark.parametrize(
    "old, new",
    [
        ("https://api.github.com", "https://api.example-not-allowed.org"),  # host not on the list
        ("https://api.github.com", "http://api.github.com"),  # not https
        ("kind: http", "kind: http\nauth:\n  type: bearer\n  secret_ref: env:GH_TOKEN"),  # carries a credential
    ],
)
def test_internet_exception_is_narrow(tmp_path, old, new):
    import shutil

    shutil.copytree(RECIPES / "buzzby", tmp_path / "buzzby")
    provider = tmp_path / "buzzby" / "provider.yaml"
    text = provider.read_text()
    assert old in text
    provider.write_text(text.replace(old, new, 1))
    assert not is_public_read_only(load_recipe("buzzby", tmp_path))
    result = validate_recipes(tmp_path)
    assert not result.ok and any(v.rule == "recipe-placeholder" for v in result.violations)


@pytest.mark.parametrize("name", READY)
def test_cards_have_plain_names_and_meaning(name):
    recipe = load_recipe(name, RECIPES)
    assert recipe.cards, f"{name} ships no cards"
    for c in recipe.cards:
        assert CARD_ID_RE.match(c.id) and c.title.strip() and c.meaning.short.strip() and c.meaning.concept.strip()
        assert c.group in ("life", "machine")
        assert c.title == c.title.strip()
        assert not re.search(r"\b(sonarr|radarr|lidarr|prowlarr|bazarr|cleanuparr|qbittorrent|gatus|authelia|traefik|bindery|grimmory|api)\b", c.title, re.I), "plain names: TV, not Sonarr"


@pytest.mark.parametrize("name", READY)
def test_every_card_maps_its_samples(tmp_path, name):
    cases = _load_cases(name)
    store, recipe = _installed(tmp_path, name)
    card_ids = {c.id for c in recipe.cards}
    assert set(cases) == card_ids, f"samples must cover exactly the cards: missing {card_ids - set(cases)}, extra {set(cases) - card_ids}"
    for card_id, card_cases in cases.items():
        states = {c["expect"]["state"] for c in card_cases}
        assert "healthy" in states or any(s in states for s in ("needs_attention",)), f"{card_id}: needs a normal-state sample"
        assert "unavailable" in states, f"{card_id}: needs an unavailable (service down) sample"
        for case in card_cases:
            send = SampleSend(case.get("responses", {}))
            runner = Runner(store, send, clock=lambda: 1_800_000_000.0)
            env = CardService(store, runner, clock=lambda: 1_800_000_000.0).build(card_id)
            label = f"{name}/{card_id}/{case['name']}"
            assert env["source_state"] == case["expect"]["state"], f"{label}: state {env['source_state']}"
            for key, text in (case["expect"].get("values") or {}).items():
                assert env["values"].get(key, {}).get("text") == text, f"{label}: {key} = {env['values'].get(key)} want {text!r}"
            assert json.dumps(env)  # the envelope is plain JSON
            blob = json.dumps(env).lower()
            assert "127.0.0.1" not in blob and "x-api-key" not in blob, f"{label}: the envelope leaks the destination or a credential header"


@pytest.mark.parametrize("name", PLANNED and [i.name for i in PLANNED] or ["_none"])
def test_planned_recipes_say_why_and_do_not_install(tmp_path, name):
    if name == "_none":
        pytest.skip("no planned recipes")
    info = next(i for i in PLANNED if i.name == name)
    assert info.note.strip(), "a planned recipe must say what it is waiting for"
    from personal_world.worlds.recipes import RecipeError

    with pytest.raises(RecipeError):
        install(ConfigStore(tmp_path / "cfg"), load_recipe(name, RECIPES), base_url="http://127.0.0.1:9")


# ---- privacy: nothing private in a public recipe, sample or doc ------------------------------------------------

# A dotted name ending in a real-looking TLD; the whole name is captured so "x.lan.example" is read as one name.
DOMAINLIKE = re.compile(r"\b(?:[a-z0-9][a-z0-9-]*\.)+(?:com|org|net|io|dev|app|xyz|me|cc|co|uk|de|duckdns|local|home|lan|internal|ts|example)\b", re.I)
URLISH = re.compile(r"https?://([^/\s\"'>]+)")
FORBIDDEN_WORDS = ("duckdns", "hulgan", "tailscale", "headscale", "amnezia", "candy", "tracker", "passkey", "magnet:")


def _public_files():
    files = [p for p in RECIPES.rglob("*") if p.is_file()]
    files += [p for p in SAMPLES.glob("*.yaml")]
    files += [ROOT / "docs" / "recipes" / "README.md"]
    return [f for f in files if f.is_file()]


@pytest.mark.parametrize("path", _public_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_private_names_in_public_recipe_files(path):
    text = path.read_text(encoding="utf-8")
    low = text.lower()
    for word in FORBIDDEN_WORDS:
        assert word not in low, f"{path.name}: contains {word!r}; keep private specifics out of this repo"
    for host in URLISH.findall(text):
        h = host.split(":")[0].lower()
        assert h.endswith(".example") or h in ("127.0.0.1", "localhost") or h in PUBLIC_READ_ONLY_HOSTS, f"{path.name}: real-looking host {host!r}"
    for m in DOMAINLIKE.findall(text.replace("network.lan", "")):
        assert m.lower().endswith(".example") or m.lower().startswith(("example.",)) or m.lower() in PUBLIC_READ_ONLY_HOSTS, f"{path.name}: domain-like text {m!r}"
