"""Lab deploy provider: consume deploy status and history via the lab CLI.

Read-only: shells out to `lab deploy status --json` and
`lab deploy ledger --json`. No mutations.
"""

import json
import subprocess  # nosec B404  # drives the operator's own `lab` CLI, argument-list form only

from ..envelope import Result, fail, ok
from .registry import StatusContract

DEFAULT_LAB = "/opt/scripts/lab"


class LabDeploy(StatusContract):
    """Deploy observation via lab CLI."""

    def __init__(self, lab_path: str | None = None) -> None:
        self.lab_path = lab_path or DEFAULT_LAB

    def _run(self, *args: str) -> dict | None:
        try:
            proc = subprocess.run(  # nosec B603  # argument list, no shell; lab_path is an operator-configured absolute path
                [self.lab_path, *args, "--json"],
                capture_output=True, text=True, timeout=30, check=True,
            )
            return json.loads(proc.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            return None

    def observe(self) -> Result:
        status = self._run("deploy", "status")
        ledger = self._run("deploy", "ledger")

        if status is None and ledger is None:
            return fail("unavailable", warnings=["lab deploy: unreachable"])

        containers = status.get("containers", []) if status else []
        running = sum(1 for c in containers if "running" in str(c.get("State", "")).lower())
        total = len(containers)

        entries = ledger.get("ledger", []) if ledger else []

        return ok(
            "healthy" if running == total else "needs_attention",
            data={
                "containers": containers,
                "running": running,
                "total": total,
                "recent_deploys": entries[-10:] if entries else [],
            },
        )

    def history(self, category: str | None = None) -> Result:
        args = ["deploy", "history"]
        if category:
            args += ["--category", category]
        data = self._run(*args)
        if data is None:
            return fail("unavailable", warnings=["lab deploy history: unreachable"])
        return ok("healthy", data=data)
