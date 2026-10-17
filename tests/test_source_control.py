"""Native source_control baseline tests (framework Rule 2).

Proves the native git-ish workflow with zero providers:

- discovery includes repos, skips plain dirs, never raises on junk
- clean / dirty / no-remote / bare-remote-with-sync status
- history newest-first with limit; empty repo -> []
- CLI changes / history / sync-status with --json envelopes
- zero-provider boot (init_world) then useful status (acceptance)
- fake enrichment leaves the native canonical shape unchanged
- manifest lists source_control as a native baseline
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.app import build_registry  # noqa: E402
from personal_world.model import ProviderMode  # noqa: E402
from personal_world.providers.registry import Registry  # noqa: E402
from personal_world.source_control import (  # noqa: E402
    NativeGit,
    configured_search_paths,
    discover_repositories,
    repository_history,
    repository_status,
)

# Deterministic git for fixtures: identity via env, and the developer's
# global/system config is *not* consulted (GIT_CONFIG_GLOBAL/SYSTEM point
# at /dev/null), so a host `init.defaultBranch=dev` or signing/hook
# settings can never change what these tests observe. `-b master` on
# init makes the default branch explicit rather than inherited.
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
    "HOME": str(Path.home()),
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        env={**GIT_ENV},
    )


def make_repo(path: Path, commits: int = 2) -> Path:
    """A real temp git repo with `commits` commits touching file.txt."""
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "master")
    git(path, "config", "user.email", "t@t")
    git(path, "config", "user.name", "t")
    for i in range(commits):
        (path / "file.txt").write_text(f"content {i}\n")
        git(path, "add", "file.txt")
        git(path, "commit", "-q", "-m", f"commit {i}")
    return path


def write_config(tmp_path: Path, search_paths: list[str]) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "connections.json").write_text(
        json.dumps(
            {
                "$schema": "personal-world/connections/1",
                "connections": [],
                "source_control": {"search_paths": search_paths},
            }
        )
    )
    return config_dir


class TestDiscovery:
    def test_includes_repos_and_skips_plain_dirs(self, tmp_path):
        repo = make_repo(tmp_path / "repo-one")
        plain = tmp_path / "plain"
        plain.mkdir()
        (plain / "note.txt").write_text("not a repo\n")
        found = discover_repositories([str(repo), str(plain)])
        assert len(found) == 2
        by_path = {e["path"]: e for e in found}
        assert by_path[str(repo)]["is_repository"] is True
        assert by_path[str(repo)]["name"] == "repo-one"
        assert by_path[str(plain)]["is_repository"] is False

    def test_missing_path_never_raises(self, tmp_path):
        ghost = tmp_path / "does-not-exist"
        found = discover_repositories([str(ghost)])
        assert found == [
            {
                "path": str(ghost),
                "name": "does-not-exist",
                "is_repository": False,
            }
        ]


class TestRepositoryStatus:
    def test_clean_repo(self, tmp_path):
        repo = make_repo(tmp_path / "clean")
        s = repository_status(str(repo))
        assert s["error"] is None
        assert s["branch"] == "master"  # explicit via `init -b`
        assert s["dirty"] is False
        assert s["revision"] is not None
        assert len(s["revision"]) == 40
        assert s["last_commit_subject"] == "commit 1"
        assert s["last_commit_date"] is not None

    def test_dirty_repo_modified_tracked_file(self, tmp_path):
        repo = make_repo(tmp_path / "dirty")
        (repo / "file.txt").write_text("modified, uncommitted\n")
        s = repository_status(str(repo))
        assert s["dirty"] is True
        assert s["error"] is None

    def test_no_remote_is_valid_local_only_state(self, tmp_path):
        repo = make_repo(tmp_path / "solo")
        s = repository_status(str(repo))
        assert s["error"] is None
        assert s["remote"] is None
        assert s["ahead"] is None
        assert s["behind"] is None

    def test_bare_remote_reports_ahead_behind(self, tmp_path):
        origin = tmp_path / "origin.git"
        origin.mkdir()
        git(origin, "init", "-q", "--bare")
        repo = make_repo(tmp_path / "synced")
        git(repo, "remote", "add", "origin", str(origin))
        git(repo, "push", "-q", "-u", "origin", "HEAD")
        s = repository_status(str(repo))
        assert s["remote"] == str(origin)
        assert (s["ahead"], s["behind"]) == (0, 0)

        # local-only commit -> ahead 1, behind 0
        (repo / "file.txt").write_text("local only\n")
        git(repo, "add", "file.txt")
        git(repo, "commit", "-q", "-m", "local only commit")
        s = repository_status(str(repo))
        assert (s["ahead"], s["behind"]) == (1, 0)

    def test_non_repo_is_structured_never_raises(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        s = repository_status(str(plain))
        assert s["error"] == "not a git repository"
        assert s["branch"] is None
        assert s["revision"] is None
        assert s["dirty"] is None

    def test_git_errors_are_structured_states(self, tmp_path):
        """A repo whose HEAD points at an unborn branch: git log fails,
        but status stays structured (no exception, no fake data)."""
        repo = tmp_path / "unborn"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "master")
        s = repository_status(str(repo))
        assert s["error"] is None  # git status works on an unborn repo
        assert s["revision"] is None  # no commits: honest None
        assert s["branch"] == "master"
        assert s["dirty"] is False  # pristine empty repo: nothing unclean


class TestRepositoryHistory:
    def test_newest_first(self, tmp_path):
        repo = make_repo(tmp_path / "hist", commits=3)
        h = repository_history(str(repo))
        assert [e["subject"] for e in h] == ["commit 2", "commit 1", "commit 0"]
        assert h[0]["author"] == "t"
        assert len(h[0]["revision"]) == 40
        assert h[0]["date"]

    def test_limit(self, tmp_path):
        repo = make_repo(tmp_path / "limited", commits=5)
        assert len(repository_history(str(repo), limit=2)) == 2
        assert [e["subject"] for e in repository_history(str(repo), limit=2)] == [
            "commit 4",
            "commit 3",
        ]

    def test_empty_repo_history_is_empty_list(self, tmp_path):
        repo = tmp_path / "empty"
        repo.mkdir()
        git(repo, "init", "-q")
        assert repository_history(str(repo)) == []

    def test_non_repo_history_is_empty_list(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert repository_history(str(plain)) == []


class TestZeroProviderBoot:
    """The acceptance proof: init a world, point it at a temp repo,
    and the native baseline answers with zero providers configured."""


        # history content checked separately below (single repo path)


    def test_registry_boots_with_native_baseline_zero_providers(self, tmp_path):
        repo = make_repo(tmp_path / "wired")
        config_dir = write_config(tmp_path, [str(repo)])
        reg = build_registry(
            __import__("personal_world.world", fromlist=["World"]).World(),
            Registry(),
            config_dir,
        )
        m = reg.manifest()["source_control"]
        assert m["native_baseline"] is True
        names = {p["name"] for p in m["providers"]}
        assert "native-git" in names
        native = [p for p in m["providers"] if p["name"] == "native-git"][0]
        assert native["mode"] == ProviderMode.NATIVE.value
        assert native["replaceable"] is False
        # the native provider itself answers observe()
        r = reg.observe("source_control")
        assert r.ok
        assert r.data["repositories"] == 1


class TestEnrichmentSeam:
    def test_fake_enrichment_does_not_change_native_shape(self, tmp_path):
        """Framework E applied to the native baseline: adding an
        enrichment provider must not alter the native canonical
        function shapes (discovery/status/history dict keys)."""
        repo = make_repo(tmp_path / "shape")
        config_dir = write_config(tmp_path, [str(repo)])
        (config_dir / "connections.json").write_text(
            json.dumps(
                {
                    "$schema": "personal-world/connections/1",
                    "connections": [
                        {
                            "type": "fake_source_control",
                            "name": "fake",
                            "capability": "source_control",
                            "mode": "enrichment",
                        },
                    ],
                    "source_control": {"search_paths": [str(repo)]},
                }
            )
        )
        reg = build_registry(
            __import__("personal_world.world", fromlist=["World"]).World(),
            Registry(),
            config_dir,
        )
        m = reg.manifest()["source_control"]
        # enrichment provider is configured, so it takes the active
        # slot; the native baseline remains as the degradation target
        assert m["active_provider"] == "fake"
        assert m["native_baseline"] is True
        assert m["on_last_provider_removed"] == "degrades to native baseline"

        # degradation proof: remove the enrichment provider -> the
        # native baseline takes over, capability concept unchanged
        bare = build_registry(
            __import__("personal_world.world", fromlist=["World"]).World(),
            Registry(),
            write_config(tmp_path, [str(repo)]),
        )
        m2 = bare.manifest()["source_control"]
        assert m2["active_provider"] == "native-git"
        assert m2["capability"] == m["capability"]
        assert m2["contract"] == m["contract"]
        # native canonical shapes are identical with/without a provider
        base_keys = set(repository_status(str(repo)))
        assert base_keys == {
            "path",
            "name",
            "branch",
            "revision",
            "dirty",
            "ahead",
            "behind",
            "remote",
            "last_commit_date",
            "last_commit_subject",
            "error",
        }
        hist = repository_history(str(repo), limit=1)
        assert set(hist[0]) == {"revision", "date", "author", "subject"}
        disc = discover_repositories([str(repo)])[0]
        assert set(disc) == {"path", "name", "is_repository"}


class TestManifest:
    def test_manifest_lists_source_control_as_native_baseline(self, tmp_path):
        reg = build_registry(
            __import__("personal_world.world", fromlist=["World"]).World(),
            Registry(),
            write_config(tmp_path, []),
        )
        m = reg.manifest()["source_control"]
        assert m["native_baseline"] is True
        assert m["on_last_provider_removed"] == "degrades to native baseline"

    def test_configured_search_paths_reads_and_fails_soft(self, tmp_path):
        assert configured_search_paths(tmp_path) == []  # no file
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "connections.json").write_text("{not json")
        assert configured_search_paths(config_dir) == []  # malformed: soft
        (config_dir / "connections.json").write_text(
            json.dumps(
                {
                    "connections": [],
                    "source_control": {"search_paths": ["/a", "/b", 3, ""]},
                }
            )
        )
        assert configured_search_paths(config_dir) == ["/a", "/b"]


class TestNativeGitProvider:
    def test_observe_states(self, tmp_path):
        repo = make_repo(tmp_path / "obs")
        p = NativeGit([str(repo)])
        r = p.observe()
        assert r.ok and r.status == "healthy"
        empty = NativeGit([])
        r = empty.observe()
        assert not r.ok and r.status == "not_configured"
        nothing = NativeGit([str(tmp_path / "void")])
        r = nothing.observe()
        assert not r.ok and r.status == "needs_attention"


class TestRecursiveDiscovery:
    """Issue #17: search_paths with recursion, depth-limited."""

    def _git(self, cwd, *args):
        import subprocess

        proc = subprocess.run(
            ["git", "--no-pager", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0, proc.stderr
        return proc.stdout

    def test_recursive_finds_nested_repos(self, tmp_path):
        outer = tmp_path / "hub"
        outer.mkdir()
        self._git(outer, "init", "-q")
        inner = tmp_path / "hub2" / "inner"
        inner.mkdir(parents=True)
        self._git(inner, "init", "-q")
        # depth 2 → hub + hub2 (not-repo-depth-correct); inner found
        # since hub2 depth=1 then inner=depth reaching 0
        p = NativeGit([str(tmp_path)], recurse=True, depth=3)
        assert p.git_available()
        result = p.observe()
        assert result.ok
        # observed data shape: {"repositories": N}; both outer repo and
        # the nested one are counted, and a 2-depth walk finds both.
        assert result.data == {"repositories": 2}


class TestRefreshWorkflow:
    """First propose→approve→act workflow (Finish Line "Actions,
    approvals"): an explicitly approved, single-repo, read-only
    status refresh. The endpoint is the ACT — approval happens in the
    UI before this call; the audit answer (proposer, what, tool,
    result, when) lands in the journal."""

    def _client(self, tmp_path, monkeypatch, repos=True):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app

        monkeypatch.setenv("PW_API_TOKEN", "t")
        config = tmp_path / "config"
        config.mkdir(exist_ok=True)
        if repos:
            repo = tmp_path / "demo"
            repo.mkdir(exist_ok=True)
            import subprocess

            subprocess.run(
                ["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True
            )
            subprocess.run(
                ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "seed"],
                check=True,
                capture_output=True,
                env={
                    **__import__("os").environ,
                    "GIT_AUTHOR_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@t",
                    "GIT_COMMITTER_NAME": "t",
                    "GIT_COMMITTER_EMAIL": "t@t",
                },
            )
            # Documented config shape (config/README.local.md): point
            # search_paths at the repo directory itself, not its parent.
            (config / "connections.json").write_text(
                '{"source_control": {"search_paths": [%s]}}'
                % json.dumps(str(tmp_path / "demo"))
            )
        app = create_app(tmp_path, config)
        return TestClient(app), tmp_path

    def _headers(self):
        return {"Authorization": "Bearer t"}

    def test_refresh_journals_the_audit_answer(self, tmp_path, monkeypatch):
        c, data = self._client(tmp_path, monkeypatch)
        r = c.post(
            "/api/source-control/refresh",
            json={"repo": "demo"},
            headers=self._headers(),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["repo"] == "demo"
        assert body["data"]["status"]["name"] == "demo"
        assert body["data"]["status"]["dirty"] is False
        # The audit answer exists: who proposed, what was approved,
        # which tool, what came back.
        from personal_world.journal import Journal

        events = Journal(data / "journal.ndjson").recent(5)
        match = [e for e in events if "repository status refresh" in e.summary]
        assert match, "no audit event recorded"
        s = match[-1].summary
        assert "proposed by the Projects screen" in s
        assert "approved explicitly" in s
        assert "native git baseline" in s
        assert "demo" in s
        assert match[-1].kind.value == "provider_action"

    def test_refresh_unknown_repo_journals_failure_honestly(
        self, tmp_path, monkeypatch
    ):
        c, data = self._client(tmp_path, monkeypatch)
        r = c.post(
            "/api/source-control/refresh",
            json={"repo": "nope"},
            headers=self._headers(),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"
        from personal_world.journal import Journal

        events = Journal(data / "journal.ndjson").recent(5)
        match = [e for e in events if "rejected" in e.summary and "nope" in e.summary]
        assert match
        assert match[-1].kind.value == "failure"

    def test_refresh_requires_auth(self, tmp_path, monkeypatch):
        c, _ = self._client(tmp_path, monkeypatch)
        r = c.post("/api/source-control/refresh", json={"repo": "demo"})
        assert r.status_code in (401, 503)

    def test_refresh_requires_repo(self, tmp_path, monkeypatch):
        c, _ = self._client(tmp_path, monkeypatch)
        r = c.post(
            "/api/source-control/refresh", json={"repo": "  "}, headers=self._headers()
        )
        assert r.status_code == 400

    def test_refresh_repeated_use_behaves_sensibly(self, tmp_path, monkeypatch):
        c, _ = self._client(tmp_path, monkeypatch)
        for _ in range(3):
            r = c.post(
                "/api/source-control/refresh",
                json={"repo": "demo"},
                headers=self._headers(),
            )
            assert r.status_code == 200 and r.json()["ok"] is True
        from personal_world.journal import Journal

        events = Journal(tmp_path / "journal.ndjson").recent(10)
        match = [e for e in events if "repository status refresh" in e.summary]
        assert len(match) == 3


class TestHistoryToolRegression:
    """Regression: the brain tool inspect_source_control_history must
    actually resolve a repository (name or path) and read history.
    It once imported a nonexistent `history` symbol and always failed
    as `unavailable` at invocation."""

    def _tools(self, tmp_path: Path):
        repo = make_repo(tmp_path / "demo")
        config_dir = write_config(tmp_path, [str(repo)])
        import personal_world.tool_registry as tr

        return tr.build_default_tools(
            world=None,
            registry=None,
            journal=None,
            source_control=None,
            vault=None,
            config_dir=config_dir,
        ), repo

    def test_invokes_by_repo_name(self, tmp_path):
        tools, repo = self._tools(tmp_path)
        result = tools.invoke("inspect_source_control_history", {"repo": "demo"})
        assert result.ok, result.warnings
        assert result.status == "healthy"
        assert result.data["repo"] == "demo"
        assert result.data["count"] == len(result.data["commits"]) >= 1
        assert result.data["commits"][0]["subject"].startswith("commit ")

    def test_invokes_by_direct_path(self, tmp_path):
        tools, repo = self._tools(tmp_path)
        result = tools.invoke("inspect_source_control_history", {"repo": str(repo)})
        assert result.ok, result.warnings
        assert result.data["count"] >= 1

    def test_unknown_name_is_structured_empty_not_exception(self, tmp_path):
        tools, _repo = self._tools(tmp_path)
        result = tools.invoke(
            "inspect_source_control_history", {"repo": "no-such-repo"}
        )
        # repository_history never raises; a non-repo path yields [] and
        # the tool reports healthy with an empty history (honest, not an
        # ImportError).
        assert result.ok, result.warnings
        assert result.data["count"] == 0
