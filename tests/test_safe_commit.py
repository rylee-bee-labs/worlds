"""P0.9: scripts/safe-commit.sh must actually work in the case it exists
for — a clean, bounded commit of exactly the named paths.

The original aborted silently (exit 1, no output) whenever the last
dirty file was one of the named paths, because the `while` loop's final
`[ skip -eq 0 ] && printf` evaluated false under `set -e`. It also
lacked the executable bit. These tests drive the script against a
throwaway git repo with pytest disabled via PW_SAFE_COMMIT_SKIP_TESTS.
"""
import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "safe-commit.sh"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "PW_SAFE_COMMIT_SKIP_TESTS": "1",
    "PATH": os.environ.get("PATH", ""),
    "HOME": os.environ.get("HOME", "/tmp"),
}


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV,
                          capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "master")
    (tmp_path / "base.txt").write_text("base\n")
    _git(tmp_path, "add", "base.txt")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _run(repo, *args):
    return subprocess.run(["sh", str(SCRIPT), *args], cwd=repo, env=GIT_ENV,
                          capture_output=True, text=True)


def test_script_is_executable():
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/safe-commit.sh must be executable"


def test_clean_bounded_commit_of_named_paths_only(repo):
    """Only named paths are dirty → the script must commit them."""
    (repo / "docs").mkdir()
    (repo / "docs" / "a.md").write_text("a\n")
    (repo / "b.txt").write_text("b\n")
    r = _run(repo, "-m", "docs: a and b", "docs/a.md", "b.txt")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "committed 2 path(s)" in r.stdout
    assert _git(repo, "log", "--format=%s", "-1").strip() == "docs: a and b"
    assert set(_git(repo, "show", "--name-only", "--format=", "HEAD").split()) == {
        "docs/a.md", "b.txt"}
    assert _git(repo, "status", "--porcelain").strip() == ""


def test_last_dirty_file_being_a_named_path_does_not_abort(repo):
    """The exact regression: named path sorts last in `git status`."""
    (repo / "aaa-other.txt").write_text("wip\n")   # someone else's WIP
    (repo / "zzz-mine.txt").write_text("mine\n")   # ours, sorts last
    r = _run(repo, "-m", "mine", "zzz-mine.txt")
    assert r.returncode == 0, (r.stdout, r.stderr)
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert committed == ["zzz-mine.txt"]
    # the other WIP is untouched and unstaged
    assert "?? aaa-other.txt" in _git(repo, "status", "--porcelain")


def test_refuses_when_more_than_five_unrelated_files_are_dirty(repo):
    for i in range(6):
        (repo / f"wip{i}.txt").write_text("x\n")
    (repo / "mine.txt").write_text("m\n")
    r = _run(repo, "-m", "mine", "mine.txt")
    assert r.returncode == 1
    assert "6 modified files outside the given paths" in r.stderr
    assert _git(repo, "log", "--format=%s", "-1").strip() == "base"


def test_force_overrides_the_guard(repo):
    for i in range(6):
        (repo / f"wip{i}.txt").write_text("x\n")
    (repo / "mine.txt").write_text("m\n")
    r = _run(repo, "--force", "-m", "mine", "mine.txt")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").split() == ["mine.txt"]


def test_usage_errors(repo):
    assert _run(repo).returncode == 2
    assert _run(repo, "-m", "x", "missing.txt").returncode == 2
    (repo / "f.txt").write_text("f\n")
    r = _run(repo, "f.txt")  # no -m
    assert r.returncode == 2 and "-m" in r.stderr


def test_failing_tests_block_the_commit(repo, monkeypatch):
    """With tests enabled and `uv` failing, nothing is staged or committed."""
    (repo / "f.txt").write_text("f\n")
    fake_bin = repo / "bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text("#!/bin/sh\nexit 1\n")
    fake_uv.chmod(0o755)
    env = {**GIT_ENV, "PW_SAFE_COMMIT_SKIP_TESTS": "0",
           "PATH": f"{fake_bin}:{GIT_ENV['PATH']}"}
    r = subprocess.run(["sh", str(SCRIPT), "-m", "f", "f.txt"], cwd=repo,
                       env=env, capture_output=True, text=True)
    assert r.returncode == 1
    assert "pytest failed" in r.stderr
    assert _git(repo, "diff", "--cached", "--name-only").strip() == ""


def test_untracked_directory_counts_once_and_named_file_inside_new_dir_is_ours(repo):
    """A large untracked tree (e.g. an uncommitted frontend prototype)
    must count as ONE outside item, and a named new file inside a brand
    new directory must not count against the guard at all."""
    proto = repo / "proto"
    for i in range(20):
        (proto / f"f{i}.txt").parent.mkdir(exist_ok=True)
        (proto / f"f{i}.txt").write_text("x\n")
    (repo / "docs" / "p1").mkdir(parents=True)
    (repo / "docs" / "p1" / "SPEC.md").write_text("spec\n")
    r = _run(repo, "-m", "spec", "docs/p1/SPEC.md")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").split() == ["docs/p1/SPEC.md"]
    assert "?? proto/" in _git(repo, "status", "--porcelain")
