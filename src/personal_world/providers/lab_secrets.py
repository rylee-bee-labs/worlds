"""Lab secrets provider: consume secret audit data via the lab CLI.

Read-only: shells out to `lab secret audit --json`. Never exposes values.
"""

import json
import subprocess  # nosec B404  # drives the operator's own `lab` CLI, argument-list form only

from ..envelope import Result, fail, ok
from .registry import StatusContract

DEFAULT_LAB = "/opt/scripts/lab"


class LabSecrets(StatusContract):
    """Secret audit observation via lab CLI."""

    def __init__(self, lab_path: str | None = None) -> None:
        self.lab_path = lab_path or DEFAULT_LAB

    def observe(self) -> Result:
        try:
            proc = subprocess.run(  # nosec B603  # argument list, no shell; lab_path is an operator-configured absolute path
                [self.lab_path, "secret", "audit", "--json"],
                capture_output=True, text=True, timeout=30, check=True,
            )
            data = json.loads(proc.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
            return fail("unavailable", warnings=[f"lab secret: {e}"])

        services = data.get("services", {})
        total = len(services)
        rendered = sum(1 for s in services.values() if s.get("rendered_on_vm"))

        return ok(
            "healthy" if rendered == total else "needs_attention",
            data={
                "total_services": total,
                "rendered": rendered,
                "sops_decryptable": data.get("sops_decryptable", False),
                "sops_key_count": data.get("sops_key_count", 0),
            },
        )
