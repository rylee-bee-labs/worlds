"""Content database provider: thin wrapper around agent-config's
ContentMaster for the personal-world Registry/Contract pattern.

The core DB logic is in agent-config. This module adapts it to
personal-world's Result envelope and provider registry.
"""

from pathlib import Path
from typing import Any

from ..envelope import Result, fail, ok
from ..status import Status
from .registry import Contract

# Try to import from agent-config. If not installed, the provider
# reports unavailable — never pretends.
try:
    import sys

    # agent-config is a sibling repo, not a pip package.
    # Add its src/ to the path if it exists.
    _AC_SRC = Path(__file__).resolve().parents[4] / "agent-config" / "src"
    if _AC_SRC.is_dir() and str(_AC_SRC) not in sys.path:
        sys.path.insert(0, str(_AC_SRC))
    from agent_config.content_master import ContentMaster

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class ContentDBProvider(Contract):
    """Content database capability via agent-config's ContentMaster."""

    def __init__(
        self,
        master_db_path: Path,
        code_root: Path | None = None,
    ):
        self._master: Any = None
        self._master_db_path = master_db_path
        self._code_root = code_root

    def _get_master(self) -> Any:
        if not _AVAILABLE:
            return None
        if self._master is None:
            self._master = ContentMaster(
                self._master_db_path, code_root=self._code_root
            )
        return self._master

    def search(
        self,
        query: str,
        *,
        kind: str | None = None,
        repo: str | None = None,
        limit: int = 20,
    ) -> Result:
        """Search across all indexed repos."""
        master = self._get_master()
        if master is None:
            return fail(
                Status.UNAVAILABLE.value,
                warnings=["content DB unavailable: agent-config not importable"],
            )
        try:
            result = master.search(query, kind=kind, repo=repo, limit=limit)
            return ok(Status.HEALTHY.value, data=result)
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"content search: {e}"])

    def discover(self, root: Path | None = None, *, force: bool = False) -> Result:
        """Scan repos and index content."""
        master = self._get_master()
        if master is None:
            return fail(
                Status.UNAVAILABLE.value,
                warnings=["content DB unavailable: agent-config not importable"],
            )
        try:
            result = master.discover(root, force=force)
            return ok(Status.HEALTHY.value, data=result)
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"content discover: {e}"])

    def list_repos(self) -> Result:
        """List registered repos."""
        master = self._get_master()
        if master is None:
            return fail(Status.UNAVAILABLE.value, warnings=["content DB unavailable"])
        try:
            return ok(Status.HEALTHY.value, data=master.list_repos())
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"content repos: {e}"])

    def store(
        self, repo_name: str, path: str, kind: str, body: str, **kwargs: Any
    ) -> Result:
        """Store content in a repo's DB."""
        master = self._get_master()
        if master is None:
            return fail(Status.UNAVAILABLE.value, warnings=["content DB unavailable"])
        try:
            master.store(repo_name, path, kind, body, **kwargs)
            return ok(Status.HEALTHY.value, data={"stored": True})
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"content store: {e}"])

    def observe(self) -> Result:
        """Report content DB status."""
        master = self._get_master()
        if master is None:
            return fail(
                Status.UNAVAILABLE.value,
                warnings=["content DB unavailable: agent-config not importable"],
            )
        try:
            stats = master.stats()
            return ok(
                Status.HEALTHY.value,
                data={
                    "provider": "content_db",
                    "backend": "sqlite_fts5",
                    "master": str(self._master_db_path),
                    **stats,
                },
            )
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"content DB: {e}"])

    def health(self) -> bool:
        if not _AVAILABLE:
            return False
        try:
            master = self._get_master()
            return master is not None
        except Exception:
            return False
