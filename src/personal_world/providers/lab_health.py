"""Lab health provider: consume health check data via the lab CLI.

Read-only: shells out to `lab health check --json`. No mutations.
"""

import json
import subprocess  # nosec B404  # drives the operator's own `lab` CLI, argument-list form only

from ..envelope import Result, fail, ok
from .registry import StatusContract

DEFAULT_LAB = "/opt/scripts/lab"


class LabHealth(StatusContract):
    """Health observation via lab CLI."""

    def __init__(self, lab_path: str | None = None) -> None:
        self.lab_path = lab_path or DEFAULT_LAB

    def observe(self) -> Result:
        try:
            proc = subprocess.run(  # nosec B603  # argument list, no shell; lab_path is an operator-configured absolute path
                [self.lab_path, "health", "check", "--json"],
                capture_output=True, text=True, timeout=30, check=True,
            )
            data = json.loads(proc.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
            return fail("unavailable", warnings=[f"lab health: {e}"])

        healthy = len(data.get("healthy", []))
        unhealthy = len(data.get("unhealthy", []))
        restarting = len(data.get("restarting", []))
        stopped = len(data.get("stopped", []))
        total = data.get("total", healthy + unhealthy + restarting + stopped)

        status = "healthy"
        if unhealthy > 0 or restarting > 0:
            status = "unhealthy"
        elif stopped > 0:
            status = "needs_attention"

        return ok(
            status,
            data={
                "total": total,
                "healthy": healthy,
                "unhealthy": unhealthy,
                "restarting": restarting,
                "stopped": stopped,
            },
        )
