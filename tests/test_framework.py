"""Framework conformance tests for the front door (ADR-0008 decision 3).

The gate ``personal-world framework validate`` is re-pointed at the new
product. These tests prove each retained rule has a passing case *and* a
failing case, that the zero-provider / zero-model baseline boots, and that
the CLI verb still returns the stable envelope and exit codes.

Every forbidden-rule import is gone: this module loads only
``personal_world.framework`` and ``personal_world.worlds.*``. The mapping
from the retired ADR-0001 rules to the rules kept here lives in
``docs/rebuild/FRAMEWORK-GATE.md``.
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.framework import (  # noqa: E402
    validate_compose_file,
    validate_config_dir,
    validate_export_rows,
    validate_framework,
    validate_memory_exports,
    validate_participant_packs,
    validate_recipes,
    validate_zero_provider_boot,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_CONFIG = REPO_ROOT / "config"
REPO_RECIPES = REPO_ROOT / "config" / "recipes"


# ---------------------------------------------------------------------------
# fixture builders (C1 files, written the same way ConfigStore reads them)
# ---------------------------------------------------------------------------


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _provider(provider_id: str = "demo", **extra) -> dict:
    data = {
        "schema_version": 1,
        "id": provider_id,
        "name": "Demo",
        "kind": "http",
        "base_url": "https://demo.lan.example",
    }
    data.update(extra)
    return data


def _request(provider_id: str = "demo", name: str = "ping", **extra) -> dict:
    data = {
        "schema_version": 1,
        "id": f"{provider_id}.{name}",
        "provider": provider_id,
        "method": "GET",
        "path": "/ping",
    }
    data.update(extra)
    return data


def _card(card_id: str = "demo-card", request_id: str = "demo.ping", **extra) -> dict:
    data = {
        "schema_version": 1,
        "id": card_id,
        "title": "Demo",
        "request": request_id,
        "meaning": {"concept": "status", "short": "Demo"},
    }
    data.update(extra)
    return data


def _valid_config_dir(tmp_path: Path) -> Path:
    root = tmp_path / "config"
    _write(root / "worlds" / "providers" / "demo.yaml", _provider())
    _write(root / "worlds" / "requests" / "demo" / "demo.ping.yaml", _request())
    _write(root / "worlds" / "cards" / "demo-card.yaml", _card())
    _write(
        root / "worlds" / "boards" / "home.yaml",
        {
            "schema_version": 1,
            "id": "home",
            "title": "Home",
            "home": True,
            "items": [{"card": "demo-card"}],
        },
    )
    return root


def _write_recipe(
    recipes_root: Path,
    name: str,
    *,
    recipe: dict | None = None,
    provider: dict | None = None,
    requests: dict[str, dict] | None = None,
) -> None:
    directory = recipes_root / name
    _write(
        directory / "recipe.yaml",
        recipe
        if recipe is not None
        else {
            "schema_version": 1,
            "name": name,
            "title": "Good",
            "summary": "A well-formed recipe.",
            "status": "ready",
            "verified": True,
            "env": ["GOOD_TOKEN"],
        },
    )
    if provider is not None:
        _write(directory / "provider.yaml", provider)
    for request_name, request in (requests or {}).items():
        _write(directory / "requests" / f"{request_name}.yaml", request)


# ---------------------------------------------------------------------------
# 1 + 2. config: real ConfigStore load, references, no inline secrets
# ---------------------------------------------------------------------------


class TestConfigRule:
    def test_valid_config_passes(self, tmp_path):
        result = validate_config_dir(_valid_config_dir(tmp_path))
        assert result.ok, [str(v) for v in result.violations]

    def test_an_empty_config_dir_passes(self, tmp_path):
        root = tmp_path / "config"
        root.mkdir()
        result = validate_config_dir(root)
        assert result.ok, [str(v) for v in result.violations]

    def test_schema_violation_is_a_config_invalid_violation(self, tmp_path):
        root = tmp_path / "config"
        _write(root / "worlds" / "providers" / "demo.yaml", _provider(bogus=1))
        result = validate_config_dir(root)
        assert not result.ok
        assert any(v.rule == "config-invalid" for v in result.violations)

    def test_dangling_reference_is_a_config_reference_violation(self, tmp_path):
        root = tmp_path / "config"
        _write(root / "worlds" / "providers" / "demo.yaml", _provider())
        _write(
            root / "worlds" / "cards" / "demo-card.yaml",
            _card(request_id="demo.missing"),
        )
        result = validate_config_dir(root)
        assert not result.ok
        assert any(v.rule == "config-reference" for v in result.violations)

    def test_inline_secret_key_on_a_request_query_is_a_secret_rule_violation(self, tmp_path):
        root = tmp_path / "config"
        _write(root / "worlds" / "providers" / "demo.yaml", _provider())
        _write(
            root / "worlds" / "requests" / "demo" / "demo.ping.yaml",
            _request(query={"api_key": "x"}),
        )
        result = validate_config_dir(root)
        assert not result.ok
        assert any(v.rule == "secret-rule" for v in result.violations)

    def test_a_symbolic_secret_ref_is_allowed(self, tmp_path):
        root = tmp_path / "config"
        _write(
            root / "worlds" / "providers" / "demo.yaml",
            _provider(auth={"type": "bearer", "secret_ref": "env:DEMO_TOKEN"}),
        )
        result = validate_config_dir(root)
        assert result.ok, [str(v) for v in result.violations]

    def test_a_non_symbolic_secret_ref_is_a_violation(self, tmp_path):
        root = tmp_path / "config"
        # The C1 model refuses this at load; it must surface as an error, not pass.
        _write(
            root / "worlds" / "providers" / "demo.yaml",
            _provider(auth={"type": "bearer", "secret_ref": "literal-value"}),
        )
        result = validate_config_dir(root)
        assert not result.ok
        assert any(
            v.rule in ("config-invalid", "secret-rule") for v in result.violations
        )

    def test_validation_never_writes_to_the_config_dir(self, tmp_path):
        root = _valid_config_dir(tmp_path)

        def snapshot() -> dict[str, bytes]:
            return {
                str(p): p.read_bytes()
                for p in sorted(root.rglob("*"))
                if p.is_file()
            }

        before = snapshot()
        result = validate_config_dir(root)
        assert result.ok
        assert snapshot() == before


# ---------------------------------------------------------------------------
# 3. shipped recipes
# ---------------------------------------------------------------------------


class TestRecipeRule:
    def test_every_shipped_recipe_passes(self):
        result = validate_recipes(REPO_RECIPES)
        assert result.ok, [str(v) for v in result.violations]

    def test_a_well_formed_recipe_passes(self, tmp_path):
        root = tmp_path / "recipes"
        _write_recipe(
            root,
            "good",
            provider=_provider("good"),
        )
        result = validate_recipes(root)
        assert result.ok, [str(v) for v in result.violations]

    def test_missing_verified_or_status_fails(self, tmp_path):
        root = tmp_path / "recipes"
        _write_recipe(
            root,
            "unverified",
            recipe={
                "schema_version": 1,
                "name": "unverified",
                "title": "Unverified",
                "summary": "No verified/status markers.",
            },
        )
        result = validate_recipes(root)
        assert not result.ok
        rules = {v.rule for v in result.violations}
        assert {"recipe-verified", "recipe-status"} <= rules

    def test_a_non_synthetic_base_url_fails(self, tmp_path):
        root = tmp_path / "recipes"
        _write_recipe(
            root,
            "realish",
            provider=_provider("realish", base_url="https://real-service.invalid"),
        )
        result = validate_recipes(root)
        assert not result.ok
        assert any(v.rule == "recipe-placeholder" for v in result.violations)

    def test_a_mismatched_recipe_name_fails(self, tmp_path):
        root = tmp_path / "recipes"
        _write_recipe(
            root,
            "directory-name",
            recipe={
                "schema_version": 1,
                "name": "other-name",
                "title": "Mismatch",
                "summary": "The directory and name disagree.",
                "status": "ready",
                "verified": True,
            },
            provider=_provider("other-name"),
        )
        result = validate_recipes(root)
        assert not result.ok
        assert any(v.rule == "recipe-invalid" for v in result.violations)

    def test_a_missing_recipes_dir_fails_discovery(self, tmp_path):
        result = validate_recipes(tmp_path / "no-such-recipes")
        assert not result.ok
        assert any(v.rule == "recipe-discovery" for v in result.violations)

    def test_an_inline_secret_key_in_a_recipe_request_fails(self, tmp_path):
        root = tmp_path / "recipes"
        _write_recipe(
            root,
            "leaky",
            provider=_provider("leaky"),
            requests={
                "leaky.secret": _request(
                    "leaky", "secret", query={"password": "x"}
                )
            },
        )
        result = validate_recipes(root)
        assert not result.ok
        assert any(v.rule == "secret-rule" for v in result.violations)


# ---------------------------------------------------------------------------
# 5. compose: no provider boot dependency
# ---------------------------------------------------------------------------


class TestComposeRule:
    def test_compose_without_provider_dependency_passes(self, tmp_path):
        path = tmp_path / "compose.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "services": {
                        "core": {"image": "core"},
                        "provider-a": {"image": "provider-a", "depends_on": ["core"]},
                    }
                }
            ),
            encoding="utf-8",
        )
        result = validate_compose_file(path, {"provider-a"})
        assert result.ok, [str(v) for v in result.violations]

    def test_core_depending_on_a_provider_fails(self, tmp_path):
        path = tmp_path / "compose.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "services": {
                        "core": {"image": "core", "depends_on": ["provider-a"]},
                        "provider-a": {"image": "provider-a"},
                    }
                }
            ),
            encoding="utf-8",
        )
        result = validate_compose_file(path, {"provider-a"})
        assert not result.ok
        assert any(v.rule == "compose-additive" for v in result.violations)

    def test_the_repo_compose_has_no_provider_boot_dependency(self):
        result = validate_compose_file(REPO_ROOT / "compose.yaml", set())
        assert result.ok, [str(v) for v in result.violations]

    def test_a_missing_compose_file_is_not_a_violation(self, tmp_path):
        result = validate_compose_file(tmp_path / "absent.yaml", set())
        assert result.ok


# ---------------------------------------------------------------------------
# 4. zero-provider / zero-model baseline boot
# ---------------------------------------------------------------------------


class TestZeroProviderBoot:
    def test_the_zero_provider_baseline_boots(self):
        result = validate_zero_provider_boot()
        assert result.ok, [str(v) for v in result.violations]

    def test_the_baseline_answers_healthz_and_the_home_board(self, tmp_path):
        from fastapi.testclient import TestClient

        from personal_world.worlds.server import build_app

        app = build_app(
            tmp_path / "config", principal_dependency=lambda: "owner"
        )
        client = TestClient(app)

        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json().get("ok") is True

        home = client.get("/api/boards/home")
        assert home.status_code == 200
        assert home.json().get("first_run") is True

    def test_a_broken_app_is_a_boot_baseline_violation(self):
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        def broken(_config_dir):
            app = FastAPI()

            @app.get("/healthz")
            def _healthz():
                return JSONResponse({"ok": False})

            @app.get("/api/boards/home")
            def _home():
                return JSONResponse({"id": "home", "items": [], "first_run": False})

            return app

        result = validate_zero_provider_boot(app_factory=broken)
        assert not result.ok
        assert any(v.rule == "boot-baseline" for v in result.violations)


# ---------------------------------------------------------------------------
# 6. shareable Memory exports carry no secret-bearing key/value
# ---------------------------------------------------------------------------


class TestExportRule:
    def test_clean_rows_pass(self):
        result = validate_export_rows(
            [{"id": 1, "title": "note", "table": "kept"}]
        )
        assert result.ok, [str(v) for v in result.violations]

    def test_a_secret_key_in_a_row_fails(self):
        result = validate_export_rows([{"id": 1, "api_key": "x"}])
        assert not result.ok
        assert any(v.rule == "secret-rule" for v in result.violations)

    def test_the_real_memory_export_path_passes(self):
        result = validate_memory_exports()
        assert result.ok, [str(v) for v in result.violations]


# ---------------------------------------------------------------------------
# the whole gate, composed
# ---------------------------------------------------------------------------


class TestFrameworkComposition:
    def test_the_repo_passes_the_whole_gate(self):
        result = validate_framework(REPO_CONFIG)
        assert result.ok, [str(v) for v in result.violations]

    def test_a_config_violation_fails_the_whole_gate(self, tmp_path):
        bad = tmp_path / "config"
        _write(bad / "worlds" / "providers" / "demo.yaml", _provider(bogus=1))
        result = validate_framework(bad)
        assert not result.ok
        assert any(v.rule == "config-invalid" for v in result.violations)


# ---------------------------------------------------------------------------
# CLI end-to-end: the same verb and envelope CI reads
# ---------------------------------------------------------------------------


def _cli_main(argv):
    from personal_world.cli import main

    return main(argv)


class TestCLIEndToEnd:
    def test_clean_config_reports_ok_and_exit_zero(self, tmp_path, capsys):
        config = tmp_path / "config"
        config.mkdir()
        rc = _cli_main(
            [
                "--data-dir",
                str(tmp_path / "data"),
                "--config-dir",
                str(config),
                "framework",
                "validate",
                "--json",
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["ok"] is True
        assert payload["data"]["count"] == 0
        assert payload["data"]["violations"] == []

    def test_a_violation_reports_nonzero_and_json(self, tmp_path, capsys):
        config = tmp_path / "config"
        _write(config / "worlds" / "providers" / "demo.yaml", _provider(bogus=1))
        rc = _cli_main(
            [
                "--data-dir",
                str(tmp_path / "data"),
                "--config-dir",
                str(config),
                "framework",
                "validate",
                "--json",
            ]
        )
        payload = json.loads(capsys.readouterr().out)
        assert rc != 0
        assert payload["ok"] is False
        assert payload["data"]["count"] >= 1
        assert payload["data"]["violations"][0]["rule"]


# ---------------------------------------------------------------------------
# participant packs (Play-Nice gate; ADR-0008 does not touch it)
# ---------------------------------------------------------------------------


class TestParticipantPackValidation:
    """``validate_participant_packs`` is the canonical, project-neutral
    gate for participant packs. Lives in the Python package (NOT in any
    harness config) so any agent, CI, or human can drive it. Validates
    parseability, required top-level keys, schema namespace, and id
    uniqueness — does NOT attest contracts."""

    REAL_PACKS = Path(__file__).resolve().parents[1] / ".project" / "participants"

    def test_real_packs_validate_clean(self):
        """Every existing pack in the repo must pass the validator.
        This test will fail loudly if anyone commits a malformed pack."""
        result = validate_participant_packs(self.REAL_PACKS)
        assert result.ok, [str(v) for v in result.violations]
        assert result.violations == []

    def test_missing_participants_dir_is_a_violation(self, tmp_path: Path):
        result = validate_participant_packs(tmp_path / "does-not-exist")
        assert not result.ok
        assert any(v.rule == "pack-discovery" for v in result.violations)

    def test_empty_participants_dir_is_a_violation(self, tmp_path: Path):
        result = validate_participant_packs(tmp_path)
        assert not result.ok
        assert any(v.rule == "pack-discovery" for v in result.violations)

    def test_malformed_yaml_is_a_violation(self, tmp_path: Path):
        """The exact failure mode observed twice this session: a
        participant.yaml that does not parse. The validator must
        catch it without leaving any malformed state behind."""
        (tmp_path / "broken").mkdir()
        bad = tmp_path / "broken" / "participant.yaml"
        # Tab indent + dangling colon: a real YAML parse failure.
        bad.write_text(
            "schema: play-nice/participant-v1\nid: broken\n\tmixed: [unclosed\n"
        )
        result = validate_participant_packs(tmp_path)
        assert not result.ok
        rules = {v.rule for v in result.violations}
        assert "pack-parse" in rules

    def test_missing_required_keys_is_a_violation(self, tmp_path: Path):
        (tmp_path / "x").mkdir()
        (tmp_path / "x" / "participant.yaml").write_text("name: no-id-no-schema\n")
        result = validate_participant_packs(tmp_path)
        assert not result.ok
        rules = {v.rule for v in result.violations}
        assert rules & {"pack-shape", "pack-parse"}

    def test_schema_namespace_must_start_with_play_nice(self, tmp_path: Path):
        (tmp_path / "x").mkdir()
        (tmp_path / "x" / "participant.yaml").write_text(
            "schema: some-other-namespace/v1\nid: x\n"
        )
        result = validate_participant_packs(tmp_path)
        assert not result.ok
        assert any(v.rule == "pack-schema-namespace" for v in result.violations)

    def test_duplicate_pack_id_is_a_violation(self, tmp_path: Path):
        for name in ("a", "b"):
            (tmp_path / name).mkdir()
            (tmp_path / name / "participant.yaml").write_text(
                "schema: play-nice/participant-v1\nid: duplicate\n"
            )
        result = validate_participant_packs(tmp_path)
        assert not result.ok
        assert any(v.rule == "pack-id-collision" for v in result.violations)

    def test_top_level_must_be_a_mapping(self, tmp_path: Path):
        (tmp_path / "x").mkdir()
        (tmp_path / "x" / "participant.yaml").write_text("- 1\n- 2\n")
        result = validate_participant_packs(tmp_path)
        assert not result.ok
        assert any(v.rule == "pack-shape" for v in result.violations)

    def test_well_formed_packs_pass(self, tmp_path: Path):
        for name in ("alpha", "beta"):
            (tmp_path / name).mkdir()
            (tmp_path / name / "participant.yaml").write_text(
                f"schema: play-nice/participant-v1\nid: {name}\nname: t\n"
            )
        result = validate_participant_packs(tmp_path)
        assert result.ok, [str(v) for v in result.violations]

    def test_cli_subcommand_drives_validator(self, capsys):
        """`personal-world framework validate-packs` must wire to the
        validator end-to-end (no harness-specific config)."""
        rc = _cli_main(["framework", "validate-packs"])
        out = capsys.readouterr().out
        assert rc == 0, out
        assert "healthy" in out
