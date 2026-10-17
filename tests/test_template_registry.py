"""Tests for the Brain Template System.

The template registry loads, validates, and composes templates from
config/prompts/ for the reasoning brain. Templates are durable artifacts
with Git history.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.template_registry import Template, TemplateRegistry  # noqa: E402


class TestTemplate:
    def test_to_dict(self):
        t = Template(id="core.identity", version=1, kind="core",
                     content="You are the assistant.", max_tokens=200)
        d = t.to_dict()
        assert d["id"] == "core.identity"
        assert d["version"] == 1
        assert d["kind"] == "core"
        assert d["max_tokens"] == 200
        assert d["content_length"] == len("You are the assistant.")
        assert d["source"] == "shipped"

    def test_surface_field(self):
        t = Template(id="surface.lab", version=1, kind="surface",
                     content="Lab instructions.", surface="lab")
        d = t.to_dict()
        assert d["surface"] == "lab"


class TestTemplateRegistry:
    @pytest.fixture
    def config_dir(self, tmp_path):
        d = tmp_path / "config"
        d.mkdir()
        prompts = d / "prompts" / "core"
        prompts.mkdir(parents=True)
        (prompts / "identity.md").write_text(
            "---\nid: core.identity\nversion: 1\nkind: core\nmax_tokens: 200\n---\nYou are the assistant."
        )
        (prompts / "truth.md").write_text(
            "---\nid: core.truth\nversion: 1\nkind: core\nmax_tokens: 300\n---\nNever invent evidence."
        )
        surfaces = d / "prompts" / "surfaces"
        surfaces.mkdir(parents=True)
        (surfaces / "lab.md").write_text(
            "---\nid: surface.lab\nversion: 1\nkind: surface\nsurface: lab\nmax_tokens: 400\n---\nLab instructions."
        )
        tasks = d / "prompts" / "tasks"
        tasks.mkdir(parents=True)
        (tasks / "inspect.md").write_text(
            "---\nid: task.inspect\nversion: 1\nkind: task\nmax_tokens: 200\n---\nInspect the resource."
        )
        formats = d / "prompts" / "formats"
        formats.mkdir(parents=True)
        (formats / "short.md").write_text(
            "---\nid: format.short\nversion: 1\nkind: format\nmax_tokens: 100\n---\nKeep replies short."
        )
        return d

    def test_loads_shipped_templates(self, config_dir):
        reg = TemplateRegistry(config_dir)
        assert reg.get("core.identity") is not None
        assert reg.get("core.truth") is not None
        assert reg.get("surface.lab") is not None

    def test_template_content(self, config_dir):
        reg = TemplateRegistry(config_dir)
        t = reg.get("core.identity")
        assert t.content == "You are the assistant."

    def test_list_templates(self, config_dir):
        reg = TemplateRegistry(config_dir)
        templates = reg.list_templates()
        assert len(templates) == 5
        ids = {t["id"] for t in templates}
        assert "core.identity" in ids
        assert "surface.lab" in ids

    def test_compose_core_only(self, config_dir):
        reg = TemplateRegistry(config_dir)
        result = reg.compose()
        assert "You are the assistant." in result
        assert "Never invent evidence." in result
        assert "Lab instructions." not in result

    def test_compose_with_surface(self, config_dir):
        reg = TemplateRegistry(config_dir)
        result = reg.compose(surface="lab")
        assert "You are the assistant." in result
        assert "Lab instructions." in result

    def test_compose_with_task(self, config_dir):
        reg = TemplateRegistry(config_dir)
        result = reg.compose(task="inspect")
        assert "Inspect the resource." in result

    def test_compose_with_format(self, config_dir):
        reg = TemplateRegistry(config_dir)
        result = reg.compose(format="short")
        assert "Keep replies short." in result

    def test_compose_full(self, config_dir):
        reg = TemplateRegistry(config_dir)
        result = reg.compose(surface="lab", task="inspect", format="short")
        assert "You are the assistant." in result
        assert "Lab instructions." in result
        assert "Inspect the resource." in result
        assert "Keep replies short." in result

    def test_missing_template_returns_none(self, config_dir):
        reg = TemplateRegistry(config_dir)
        assert reg.get("nonexistent") is None

    def test_missing_surface_ignored(self, config_dir):
        reg = TemplateRegistry(config_dir)
        result = reg.compose(surface="nonexistent")
        # Core templates still present
        assert "You are the assistant." in result

    def test_provenance(self, config_dir):
        reg = TemplateRegistry(config_dir)
        p = reg.provenance(surface="lab", task="inspect")
        assert len(p["core"]) == 2
        assert p["surface"]["id"] == "surface.lab"
        assert p["task"]["id"] == "task.inspect"
        assert p["overrides"] == []

    def test_private_override(self, config_dir):
        local = config_dir / "prompts.local"
        local.mkdir()
        core = local / "core"
        core.mkdir()
        (core / "identity.md").write_text(
            "---\nid: core.identity\nversion: 1\nkind: core\nmax_tokens: 200\n---\nCustom identity."
        )
        reg = TemplateRegistry(config_dir)
        t = reg.get("core.identity")
        assert t.content == "Custom identity."
        assert t.source == "private"
        # Override appears in provenance
        p = reg.provenance()
        assert any(o["id"] == "core.identity" for o in p["overrides"])

    def test_empty_config_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        reg = TemplateRegistry(d)
        assert reg.list_templates() == []
        assert reg.compose() == ""

    def test_provenance_no_args(self, config_dir):
        reg = TemplateRegistry(config_dir)
        p = reg.provenance()
        assert p["surface"] is None
        assert p["task"] is None
        assert p["packs"] == []


class TestTemplateRegistryApi:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app

        monkeypatch.setenv("PW_API_TOKEN", "t")
        # Create config with prompts
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prompts = config_dir / "prompts" / "core"
        prompts.mkdir(parents=True)
        (prompts / "identity.md").write_text(
            "---\nid: core.identity\nversion: 1\nkind: core\nmax_tokens: 200\n---\nYou are the assistant."
        )
        app = create_app(tmp_path, config_dir)
        return TestClient(app)

    def _headers(self):
        return {"Authorization": "Bearer t"}

    def test_brain_templates_endpoint(self, client):
        r = client.get("/api/brain/templates", headers=self._headers())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        templates = body["data"]["templates"]
        assert len(templates) == 1
        assert templates[0]["id"] == "core.identity"

    def test_brain_provenance_endpoint(self, client):
        r = client.get("/api/brain/provenance", headers=self._headers())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert len(body["data"]["core"]) == 1

    def test_brain_provenance_with_surface(self, client):
        r = client.get("/api/brain/provenance?surface=lab",
                       headers=self._headers())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True

    def test_brain_templates_requires_auth(self, client):
        r = client.get("/api/brain/templates")
        assert r.status_code in (401, 503)

    def test_brain_provenance_requires_auth(self, client):
        r = client.get("/api/brain/provenance")
        assert r.status_code in (401, 503)
