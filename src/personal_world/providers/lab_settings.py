"""Lab settings provider: consume the homelab Settings Reconciler
via the lab CLI.

Read-only: shells out to `lab settings status --json` and
`lab settings inspect <service> --json`. No mutations.
"""

import json
import subprocess  # nosec B404  # drives the operator's own `lab` CLI, argument-list form only

from ..envelope import Result, fail, ok
from .registry import StatusContract

DEFAULT_LAB = "/opt/scripts/lab"


class LabSettings(StatusContract):
    """Settings Reconciler observation via lab CLI."""

    def __init__(self, lab_path: str | None = None) -> None:
        self.lab_path = lab_path or DEFAULT_LAB

    def observe(self) -> Result:
        try:
            proc = subprocess.run(  # nosec B603  # argument list, no shell; lab_path is an operator-configured absolute path
                [self.lab_path, "settings", "status", "--json"],
                capture_output=True, text=True, timeout=30, check=True,
            )
            data = json.loads(proc.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
            return fail("unavailable", warnings=[f"lab settings: {e}"])

        services = data.get("services", [])
        drifted = sum(1 for s in services if s.get("status") == "DRIFT")
        total = len(services)

        return ok(
            "healthy" if drifted == 0 else "needs_attention",
            data={
                "total": total,
                "drifted": drifted,
                "healthy": total - drifted,
                "services": services,
            },
        )

    def inspect(self, service: str) -> Result:
        try:
            proc = subprocess.run(  # nosec B603  # argument list, no shell; lab_path is an operator-configured absolute path
                [self.lab_path, "settings", "inspect", service, "--json"],
                capture_output=True, text=True, timeout=15, check=True,
            )
            data = json.loads(proc.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
            return fail("unavailable", warnings=[f"lab settings inspect: {e}"])
        return ok("healthy", data=data)

    def diff(self, service: str) -> Result:
        try:
            proc = subprocess.run(  # nosec B603  # argument list, no shell; lab_path is an operator-configured absolute path
                [self.lab_path, "settings", "diff", service, "--json"],
                capture_output=True, text=True, timeout=15, check=True,
            )
            data = json.loads(proc.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
            return fail("unavailable", warnings=[f"lab settings diff: {e}"])
        return ok("healthy", data=data)
