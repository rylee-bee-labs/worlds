"""The image builds the interface: Dockerfile + .dockerignore static checks.

Owner decision 2026-09-22: the React rebuild IS the product frontend.
The image contains a node stage that builds `ui/` from this repo and
stages it at `src/personal_world/static/app/`; the vanilla Station is no
longer packaged, and no mode switch (PW_FRONTEND*, PW_STATION_DIST) may
exist. Guards here are static (no docker run) — the compose CI job does
the real build.
"""

import re
import sys
import traceback
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

REPO_ROOT = Path(__file__).parent.parent


def _dockerfile_text():
    return (REPO_ROOT / "Dockerfile").read_text()


def _dockerignore_text():
    return (REPO_ROOT / ".dockerignore").read_text()


def _publish_workflow():
    """Parse `publish-image.yml`.

    The guards below read the workflow as YAML rather than as text: a
    whole-file substring search cannot tell which job a line belongs to,
    which is exactly how a publisher can end up ungated.
    """
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "publish-image.yml").read_text())


def _triggers(workflow):
    """The workflow's top-level trigger mapping.

    PyYAML follows YAML 1.1, where the bare key `on` is the boolean
    `True`; accept either spelling.
    """
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), triggers
    return triggers


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


class TestWorldsPublishesItsOwnImage:
    """Owner decision 2026-10-26: this repository publishes the production image.

    `personal-world` is archived read-only, so it can no longer be the
    source of the image the homelab runs. `publish-image.yml` here builds
    the appliance from this repository and pushes it to
    `ghcr.io/rylee-bee-labs/worlds`, which the homelab autodeploy consumes
    as `:main`. These guards keep the repository gate and the image name
    honest: a fork must never publish into the estate's registry, and the
    archived repository must never come back as the gate.

    The guards parse the workflow as YAML and look at the job they are
    about: a whole-file substring search would still pass if the publish
    job lost its gate while the text survived somewhere else.
    """

    WF = REPO_ROOT / ".github" / "workflows" / "publish-image.yml"

    def _text(self):
        assert self.WF.exists(), "the publish workflow is missing"
        return self.WF.read_text()

    def _workflow(self):
        return _publish_workflow()

    def _publish_job(self):
        return self._workflow()["jobs"]["publish"]

    def test_publish_workflow_exists_and_pushes_the_worlds_image(self):
        text = self._text()
        assert "ghcr.io/rylee-bee-labs/worlds" in text
        assert "packages: write" in text
        assert "push: true" in text

    def test_publish_job_gates_on_this_repository(self):
        # The gate must sit on the publish job itself, not merely appear
        # somewhere in the file.
        publish_if = self._publish_job()["if"]
        assert "github.repository == 'rylee-bee-labs/worlds'" in publish_if
        # The archived repository is never the gate, and never the target.
        assert "rylee-bee-labs/personal-world" not in self._text()

    def test_publish_job_publishes_the_main_tag(self):
        # The homelab autodeploy pulls `ghcr.io/rylee-bee-labs/worlds:main`.
        # Anchored on the exact metadata-action line, so `value=manual`
        # (or any other tag ending in "main") cannot satisfy this.
        meta = next(s for s in self._publish_job()["steps"] if s.get("id") == "meta")
        tags = [line.strip() for line in meta["with"]["tags"].splitlines() if line.strip()]
        assert "type=raw,value=main" in tags, tags
        assert "type=raw,value=manual" not in tags, tags

    def test_workflow_has_no_pull_request_trigger(self):
        # `workflow_run` after `validate` on main is the only trigger: a
        # pull request (or a fork's copy of this file) must not publish.
        # Structural, not a raw-text search for the word.
        triggers = _triggers(self._workflow())
        assert "pull_request" not in triggers, triggers
        assert set(triggers) == {"workflow_run"}, triggers
        assert triggers["workflow_run"]["workflows"] == ["validate"], triggers

    def test_publish_job_refuses_a_stale_validated_sha(self):
        """A `validate` run for an older commit must not reset `:main`."""
        publish = self._publish_job()
        steps = publish["steps"]
        body = yaml.safe_dump(publish, sort_keys=False)
        # The guard lives in the publish job and asks for main's current tip.
        assert "commits/main" in body, body
        assert "stale" in body.lower(), body
        names = [s.get("name", "") for s in steps]
        guard = next(i for i, n in enumerate(names) if "stale" in n.lower())
        build = next(
            i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("docker/build-push-action")
        )
        assert guard < build, names
        guard_step = steps[guard]
        assert guard_step.get("id") == "freshness"
        # It compares the validated SHA with main's tip, using the job token.
        assert "secrets.GITHUB_TOKEN" in guard_step["env"]["GH_TOKEN"]
        run = guard_step["run"]
        assert "HEAD_SHA" in run
        assert "!=" in run
        assert "skip=true" in run
        # Everything after the guard is gated on its verdict.
        for step in steps[guard + 1 :]:
            assert step.get("if") == "steps.freshness.outputs.skip != 'true'", step.get("name")

    def test_not_shipped_pattern_excludes_spec_files(self):
        """Test-only files must skip the build, vitest's `*.spec.ts(x)` included."""
        changes = self._workflow()["jobs"]["changes"]
        script = "\n".join(s.get("run", "") for s in changes["steps"])
        match = re.search(r"NOT_SHIPPED='([^']+)'", script)
        assert match, script
        not_shipped = re.compile(match.group(1))
        for path in (
            "ui/src/app/thing.spec.ts",
            "ui/src/app/thing.spec.tsx",
            "ui/src/app/thing.test.ts",
            "ui/src/app/thing.test.tsx",
            "ui/src/app/thing.stories.tsx",
        ):
            assert not_shipped.search(path), path
        for path in ("ui/src/app/thing.ts", "ui/src/app/thing.tsx"):
            assert not not_shipped.search(path), path

    def test_no_manual_republish_path_is_promised(self):
        """The comment must not promise a path the gates exclude.

        Only a re-run of a push-triggered `validate` run re-fires this
        workflow; `validate` has no `workflow_dispatch` trigger and the
        `workflow_run.event == 'push'` gate would exclude one anyway, so
        there is no manual republish path today.
        """
        triggers = _triggers(self._workflow())
        assert "workflow_dispatch" not in triggers, triggers
        changes_if = self._workflow()["jobs"]["changes"]["if"]
        assert "github.event.workflow_run.event == 'push'" in changes_if
        # The header comment, unwrapped, so re-wrapping the prose cannot
        # quietly change what it claims.
        comment = " ".join(
            line.lstrip("#").strip()
            for line in self._text().splitlines()
            if line.lstrip().startswith("#")
        )
        assert "no manual republish path" in comment, comment
        assert "Re-running the `validate` workflow on main" not in comment

    def test_only_the_publish_workflow_pushes_an_image(self):
        pushers = [
            wf.name
            for wf in (REPO_ROOT / ".github" / "workflows").glob("*.yml")
            if "push: true" in wf.read_text()
        ]
        assert pushers == ["publish-image.yml"], pushers


def _main():
    """Run this module's guards without pytest.

    `python3 tests/test_dockerfile.py` runs exactly the classes pytest
    would collect here, so the image's static contract can be checked on a
    machine with no pytest installed. The repository's documented command
    remains `uv run pytest --timeout=30` (see AGENTS.md).
    """
    failures = []
    ran = 0
    for name, obj in sorted(globals().items()):
        if not (isinstance(obj, type) and name.startswith("Test")):
            continue
        for method in sorted(dir(obj)):
            if not method.startswith("test_"):
                continue
            ran += 1
            try:
                getattr(obj(), method)()
            except Exception:  # report every failure, then exit non-zero
                failures.append(f"{name}::{method}\n{traceback.format_exc()}")
                print(f"FAIL {name}::{method}")
            else:
                print(f"pass {name}::{method}")
    print(f"\n{ran - len(failures)}/{ran} passed")
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
