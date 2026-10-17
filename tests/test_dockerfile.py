"""The image builds the interface: Dockerfile + .dockerignore static checks.

Owner decision 2026-09-22: the React rebuild IS the product frontend.
The image contains a node stage that builds `ui/` from this repo and
stages it at `src/personal_world/static/app/`; the vanilla Station is no
longer packaged, and no mode switch (PW_FRONTEND*, PW_STATION_DIST) may
exist. Guards here are static (no docker run) — the compose CI job does
the real build.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

REPO_ROOT = Path(__file__).parent.parent


def _dockerfile_text():
    return (REPO_ROOT / "Dockerfile").read_text()


def _dockerignore_text():
    return (REPO_ROOT / ".dockerignore").read_text()


class TestDockerfile:
    def test_ui_build_stage_exists(self):
        text = _dockerfile_text()
        assert "FROM node:" in text
        assert "AS ui-build" in text
        assert "npm ci" in text
        assert "npm run build" in text

    def test_interface_staged_from_stage(self):
        text = _dockerfile_text()
        assert "COPY --from=ui-build /src/ui/dist ./src/personal_world/static/app" in text
        assert "test -f src/personal_world/static/app/index.html" in text

    def test_vanilla_station_not_packaged(self):
        # The retired interface must not come back through the image.
        assert "COPY design/opendesign-exploration/station" not in _dockerfile_text()

    def test_no_mode_switches(self):
        text = _dockerfile_text()
        for banned in ("PW_FRONTEND", "PW_STATION_DIST", "PW_VNEXT_DIST", "PW_FRONTEND_TARGET"):
            assert banned not in text, banned
        api_src = (REPO_ROOT / "src" / "personal_world" / "api.py").read_text()
        assert 'os.environ.get("PW_FRONTEND"' not in api_src

    def test_runtime_stage_unchanged_essentials(self):
        text = _dockerfile_text()
        assert "FROM python:3.12-slim-bookworm" in text
        assert "HEALTHCHECK" in text
        # Production auth is owner.yaml bootstrap (worlds/production.py:app_from_env);
        # the old token-gated create_app is gone.
        assert "uvicorn personal_world.worlds.production:app_from_env --factory" in text
        assert "personal_world.api:create_app" not in text
        # The boot-time PW_API_TOKEN guard stays, deliberately separate from the
        # owner.yaml bootstrap: a container with no token at all is a
        # misconfiguration we want to hear about at boot, not serve. Asserted
        # here and behaviourally in test_safety.py::TestEntrypointTokenGuard.
        assert "FATAL: PW_API_TOKEN is empty or unset" in text
        froms = [line for line in text.splitlines() if line.startswith("FROM ")]
        assert len(froms) == 2
        assert all("@sha256:" in line for line in froms), froms


class TestImageContents:
    def test_runtime_image_has_no_test_extra(self):
        text = _dockerfile_text()
        sync = [line for line in text.splitlines() if "uv sync" in line]
        assert sync and all("--extra test" not in line for line in sync), sync
        assert any("--extra crypto" in line for line in sync)


class TestDockerignore:
    def test_private_material_excluded(self):
        text = _dockerignore_text()
        # **/.env is recursive on purpose: ui/.env is read by Vite at
        # build time and inlined into the public bundle.
        for needle in (
            "**/.env",
            "**/.env.*",
            "data/",
            "config/*.local.json",
            "config/principal.json",
            "**/node_modules",
            ".git",
            ".venv",
            "*.log",
            "design/exports/",
            ".pytest_cache",
        ):
            assert needle in text, needle

    def test_local_staged_build_excluded(self):
        # The image's ui-build stage is the only source of static/app;
        # a stale local staging must never ride in via COPY src.
        assert "src/personal_world/static/app/" in _dockerignore_text()


class TestWorkflowPins:
    def test_reusable_workflows_are_pinned_to_commits(self):
        import re

        for wf in (REPO_ROOT / ".github" / "workflows").glob("*.yml"):
            for line in wf.read_text().splitlines():
                m = re.search(r"uses:\s*(\S+)@(\S+)", line)
                if m and "/.github/workflows/" in m.group(1):
                    assert re.fullmatch(r"[0-9a-f]{40}", m.group(2)), f"{wf.name}: {line.strip()}"

    def test_image_publish_records_provenance(self):
        text = (REPO_ROOT / ".github" / "workflows" / "publish-image.yml").read_text()
        assert "provenance: true" in text
