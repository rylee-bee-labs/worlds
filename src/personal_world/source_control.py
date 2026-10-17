"""Native source_control baseline: read-only local git discovery,
status, and history.

Capabilities are core-owned (framework Rule 2): with zero providers
connected, this module gives the capability useful local meaning from
the local `git` binary alone. This local baseline is canonical. A
provider (e.g. the optional GitHub enrichment) may enrich the
capability with remote-side richness, but the native canonical shape
below is unchanged by enrichment — local truth survives the remote
provider.

Safety contract:

- subprocess with explicit argument lists only; never shell=True
- every call is `git --no-pager -C <path> ...` and read-only
- 10s timeout per call
- every git failure becomes a structured state, never an exception
"""

import json
import os
import shutil
import subprocess  # nosec B404  # drives the operator's own `git`, argument-list form only
from pathlib import Path

from .envelope import Result, fail, ok
from .providers.registry import SourceControlContract

GIT_TIMEOUT_SECONDS = 10


def _git(path: Path, *args: str) -> tuple[int, str, str]:
    """Run one read-only git command. Returns (returncode, stdout,
    stderr); returncode is -1 when the git binary is missing or the
    call times out. Never raises for git failures."""
    try:
        proc = subprocess.run(  # nosec  # B603 and B607 both apply to this call — argument list, no shell; `git` is the operator's own binary on PATH
            ["git", "--no-pager", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", f"git unavailable: {e}"
    return proc.returncode, proc.stdout, proc.stderr


def _is_repository(path: Path) -> bool:
    rc, _out, _err = _git(path, "rev-parse", "--git-dir")
    return rc == 0


def _branch(path: Path) -> str | None:
    rc, out, _err = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
    if rc == 0:
        return out.strip()
    # unborn branch (no commits yet): rev-parse fails, symbolic-ref works
    rc, out, _err = _git(path, "symbolic-ref", "--short", "HEAD")
    if rc == 0:
        return out.strip()
    return None


def _remote_url(path: Path) -> str | None:
    rc, out, _err = _git(path, "remote", "get-url", "origin")
    if rc == 0:
        return out.strip() or None
    rc, out, _err = _git(path, "remote")
    if rc == 0:
        names = out.split()
        if names:
            rc, out, _err = _git(path, "remote", "get-url", names[0])
            if rc == 0:
                return out.strip() or None
    return None


def _upstream_counts(
    path: Path, branch: str | None
) -> tuple[int | None, int | None]:
    """(ahead, behind) against the tracking upstream. None/None when no
    remote tracking ref exists -- valid local-only state, not an error."""
    specs = ["@{upstream}"]
    if branch:
        specs.append(f"origin/{branch}")
    for spec in specs:
        rc, out, _err = _git(
            path, "rev-list", "--left-right", "--count", f"{spec}...HEAD"
        )
        if rc == 0:
            parts = out.split()
            if len(parts) == 2:
                try:
                    behind, ahead = int(parts[0]), int(parts[1])
                except ValueError:
                    return None, None
                return ahead, behind
    return None, None


def discover_repositories(
    search_paths: list[str], recurse: bool = False, depth: int = 2
) -> list[dict]:
    """Check each configured path directly. Plain directories come back
    with is_repository False (skipped by status workflows, never hidden
    from the caller); missing or unreadable paths never raise.

    With ``recurse`` set (via the configured ``source_control.recursive``
    flag; default False to preserve the hard-coded "explicit only"
    behavior), each search path is walked depth-limited (default 2) to
    find nested checkouts. A directory with its own ``.git`` stops the
    walk (inner-repo inner-dir not entered)."""
    out: list[dict] = []
    seen: set[str] = set()

    def visit(p: Path, remaining: int) -> None:
        if str(p) in seen:
            return
        seen.add(str(p))
        is_repo = _is_repository(p)
        out.append({
            "path": str(p),
            "name": p.name,
            "is_repository": is_repo,
        })
        if remaining <= 0:
            return
        try:
            entries = sorted(p.iterdir())
        except OSError:
            return
        for child in entries:
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            if is_repo:
                # inside a repo, don't descend further (tracked checkout)
                continue
            visit(child, remaining - 1)

    for raw in search_paths:
        p = Path(raw).expanduser()
        if recurse:
            visit(p, depth)
        else:
            out.append({
                "path": str(p),
                "name": p.name,
                "is_repository": _is_repository(p),
            })
    return out


def repository_status(path: str) -> dict:
    """Structured status of one repository. Git errors become structured
    states (error field, component None), never exceptions."""
    p = Path(path).expanduser()
    state: dict = {
        "path": str(p),
        "name": p.name,
        "branch": None,
        "revision": None,
        "dirty": None,
        "ahead": None,
        "behind": None,
        "remote": None,
        "last_commit_date": None,
        "last_commit_subject": None,
        "error": None,
    }
    if not _is_repository(p):
        state["error"] = "not a git repository"
        return state
    rc, out, _err = _git(p, "rev-parse", "HEAD")
    if rc == 0:
        state["revision"] = out.strip()
    state["branch"] = _branch(p)
    rc, out, err = _git(p, "status", "--porcelain")
    if rc == 0:
        state["dirty"] = bool(out.strip())
    else:
        state["error"] = err.strip() or "git status failed"
    # empty repo (no commits yet) is valid local-only state, not an error
    rc, out, _err = _git(
        p, "log", "-1",
        "--pretty=format:%ad%x00%an%x00%s", "--date=iso-strict",
    )
    if rc == 0 and out:
        parts = out.split("\x00")
        if len(parts) == 3:
            state["last_commit_date"] = parts[0] or None
            state["last_commit_subject"] = parts[2] or None
    state["remote"] = _remote_url(p)
    state["ahead"], state["behind"] = _upstream_counts(p, state["branch"])
    return state


def repository_history(path: str, limit: int = 20) -> list[dict]:
    """Newest-first commit history, up to limit entries. A non-repo path
    or empty repo returns [] (structured, never raised)."""
    p = Path(path).expanduser()
    if not _is_repository(p):
        return []
    limit = max(1, int(limit))
    rc, out, _err = _git(
        p, "log", f"-n{limit}",
        "--date=iso-strict",
        "--pretty=format:%H%x00%ad%x00%an%x00%s",
    )
    if rc != 0:
        return []
    history: list[dict] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x00")
        if len(parts) != 4:
            continue
        revision, date, author, subject = parts
        history.append({
            "revision": revision,
            "date": date,
            "author": author,
            "subject": subject,
        })
    return history


def enrich_all_repositories(
    repos: list[dict], enricher=None
) -> list[dict]:
    """Remote enrichment for EVERY discovered repository, in input
    order — one entry per repository, plain directories skipped by
    design (never an error, never reported).

    Local Git stays canonical: this only ADDS remote-side facts on top
    of what repository_status already knows locally, and the native
    status shape is unchanged. 'not_github' and 'unavailable' are
    valid, non-crashing answers; a number is never guessed. A single
    repository's failure — including an enricher that raises — stays
    inside that one entry and never breaks the loop.

    ``enricher`` defaults to the optional GitHub enrichment, imported
    INSIDE this function (as api.py does) so this module keeps no
    import cycle with the providers package. Tests inject a fake.
    """
    if enricher is None:
        from .providers.github import GitHubEnrichment

        enricher = GitHubEnrichment()

    entries: list[dict] = []
    for repo in repos:
        if not repo.get("is_repository"):
            continue
        try:
            status = repository_status(repo["path"])
            r = enricher.enrich_repo(status.get("remote"))
        except Exception as err:  # never raise out of a fan-out
            r = fail(
                "unavailable",
                data={},
                warnings=[f"enrichment failed: {err}"],
            )
        entries.append({
            "name": repo.get("name"),
            "path": repo.get("path"),
            "ok": r.ok,
            "status": r.status,
            "data": r.data if isinstance(r.data, dict) else {},
            "warnings": list(r.warnings),
        })
    return entries


def status_all(search_paths: list[str]) -> list[dict]:
    """Discovery plus status for every configured path that is a
    repository; plain directories are skipped by design."""
    return [
        repository_status(entry["path"])
        for entry in discover_repositories(search_paths)
        if entry["is_repository"]
    ]


DEV_CHECKOUT_ENV = "PW_SOURCE_CONTROL_ROOT"


def current_checkout_root() -> str | None:
    """The personal-world checkout itself, portably (BATCH 7).

    Order of resolution:
    1. PW_SOURCE_CONTROL_ROOT env (explicit override; wins).
    2. This package's repository root — the directory containing the
       installed source tree (src/personal_world/...) when it is a
       working checkout (has a .git). Wheel/site-packages installs
       carry no .git and resolve to None.

    Never a hard-coded machine path. Used as an ADDITIONAL search
    path in development so the Projects surface can observe the
    checkout it is running from. Full path precedence in
    configured_search_paths: explicit config > env override > dev
    fallback; configured search paths always come first and are
    unaffected.
    """

    env_root = os.environ.get(DEV_CHECKOUT_ENV, "").strip()
    if env_root:
        return str(Path(env_root).expanduser())
    root = Path(__file__).resolve().parents[2]
    if (root / ".git").exists() and (root / "pyproject.toml").exists():
        return str(root)
    return None


def configured_search_paths(config_dir: Path) -> list[str]:
    """Read the native baseline's repo paths from
    config/connections.json under a `source_control.search_paths` key,
    alongside (not inside) the provider connections list. Malformed or
    missing config yields [] -- the native baseline still boots.

    Development ergonomics (BATCH 7): with PW_DEV_AUTH_BYPASS=1, an
    UNCONFIGURED setup is additionally offered the current Project
    Worlds checkout itself (see current_checkout_root) so a normal dev
    environment sees at least its own repository in Projects.
    Production behavior is byte-identical: unconfigured stays
    unconfigured, and an explicit config always wins."""
    paths: list[str] = []
    conn_path = Path(config_dir) / "connections.json"
    if conn_path.exists():
        try:
            payload = json.loads(conn_path.read_text())
            section = payload.get("source_control")
            if isinstance(section, dict):
                raw = section.get("search_paths")
                if isinstance(raw, list):
                    paths = [str(p) for p in raw if isinstance(p, str) and p]
        except (json.JSONDecodeError, OSError):
            pass
    if not paths:
        from .identity import dev_bypass_enabled
        if dev_bypass_enabled():
            # env override (dev ergonomics) first, then the checkout
            env_root = os.environ.get(DEV_CHECKOUT_ENV, "").strip()
            if env_root:
                return [str(Path(env_root).expanduser())]
            checkout = current_checkout_root()
            if checkout:
                return [checkout]
    return paths


def config_recursive_flag(config_dir: Path) -> bool:
    """Optional drive for multi-repo discovery. Config key:
    `source_control.recursive` (defaults False; explicit-only
    indexes stay the canonical behavior)."""
    conn_path = Path(config_dir) / "connections.json"
    if not conn_path.exists():
        return False
    try:
        payload = json.loads(conn_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    section = payload.get("source_control")
    if not isinstance(section, dict):
        return False
    return bool(section.get("recursive"))


class NativeGit(SourceControlContract):
    """Native baseline provider for source_control: the local git
    binary, zero external services, zero secrets. Registered with
    ProviderMode.NATIVE; enrichment providers never replace it."""

    def __init__(self, search_paths: list[str], recurse: bool = False, depth: int = 2) -> None:
        self.search_paths = list(search_paths)
        self.recurse = recurse
        self.depth = depth

    def git_available(self) -> bool:
        return shutil.which("git") is not None

    def observe(self) -> Result:
        if not self.git_available():
            return fail(
                "unavailable", warnings=["git binary not found"],
            )
        if not self.search_paths:
            return fail(
                "not_configured",
                warnings=["no source_control search paths configured"],
            )
        repos = [
            entry for entry in discover_repositories(
                self.search_paths, recurse=self.recurse, depth=self.depth
            )
            if entry["is_repository"]
        ]
        if not repos:
            return Result(
                ok=False,
                status="needs_attention",
                warnings=["no git repositories found in configured "
                          "search paths"],
            )
        return ok("healthy", data={"repositories": len(repos)})
