"""Workbench provider: distrobox/podman containers as attached
workspaces (ADR-0003 thin-slice spike, backend only).

OFF BY DEFAULT. PW_WORKBENCH=1 registers the provider; without it the
capability reports not_configured like every other unconnected
capability (zero-provider boot preserved, ADR-0003 Rule 2).

Trust-class minimum — the terminal/exec broker boundary (ADR-0003 D4),
non-negotiable and each item proven by tests/test_workbench_spike.py:
- container must match an explicit allowlist (default: empty -> run_task
  refuses everything; fail closed);
- the task is a bounded argv LIST passed straight to `podman exec`,
  never a shell string: no interpolation, no pipes, no globbing;
- the podman client runs with an explicit EMPTY environment by default:
  host secrets cannot ride through; extra env is an opt-in config
  allowlist, never inheritance;
- no mount/volume flags are ever assembled: host paths stay on the host;
- execution is bounded by a timeout (clamped to max_timeout);
- every attempted task is recorded as a TASK event on the journal using
  the ADR-0006 envelope (event_id/task_id/state/payload/correlation_id);
  refusals are recorded as SECURITY events; run_task REFUSES to execute
  at all when no journal is wired (unauditable work does not run).

Read side (list_environments) is read-only and degrades to
'unavailable: <reason>' on any error — never a fake list.

This is a spike: no attach/streaming, no network exposure, no routes.
Findings and the owner's open decisions: docs/adr/WORKBENCH-SPIKE-FINDINGS.md.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404  # drives the operator's own container/agent tooling, argument-list form only
import uuid
from typing import Any

from ..envelope import Result, fail, ok
from ..model import JournalEvent, JournalKind, Provenance, now
from ..status import Status
from .registry import StatusContract

WORKBENCH_ENV = "PW_WORKBENCH"
#: Comma-separated container names; a config-file allowlist
#: (connections.json "workbench".allowed_containers) overrides it.
ALLOWLIST_ENV = "PW_WORKBENCH_CONTAINERS"

#: Distrobox/podman container name shape: no leading dash (option
#: injection), no path separators, whitespace or shell metacharacters.
_CONTAINER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

DEFAULT_TIMEOUT = 60.0
MAX_TIMEOUT = 600.0
#: Output kept in Result.data and in the journal payload (the
#: execution_viewer precedent truncates at 10 000; the journal line
#: stays far below it).
STDOUT_CAP = 4000
STDERR_CAP = 2000


def workbench_enabled() -> bool:
    """Single source of truth for the env gate (strict truthy set —
    anything else stays off; fail closed, never a silent enable)."""
    return os.environ.get(WORKBENCH_ENV, "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class WorkbenchPodman(StatusContract):
    """Observe attached container environments; execute bounded argv
    tasks inside allowlisted containers via `podman exec`."""

    enabled = staticmethod(workbench_enabled)

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        journal=None,
    ) -> None:
        config = config or {}
        self.journal = journal
        # test/owner entry point: find this binary via PATH, no absolute default
        self.podman_bin = str(config.get("podman_bin", "podman"))
        self._allowlist_cfg = config.get("allowed_containers")
        default = config.get("default_timeout", DEFAULT_TIMEOUT)
        self.default_timeout = self._clamp(default)
        self.max_timeout = self._clamp(config.get("max_timeout", MAX_TIMEOUT))
        # explicit env for the podman client AND the exec'd task:
        # empty by default (no secret passthrough); opt-in only.
        self.exec_env = {
            str(k): str(v) for k, v in (config.get("podman_env") or {}).items()
        }

    # ── helpers ─────────────────────────────────────────────────────

    def _clamp(self, value: Any) -> float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = DEFAULT_TIMEOUT
        return max(0.1, min(v, MAX_TIMEOUT))

    def _binary(self) -> str | None:
        return shutil.which(self.podman_bin)

    def allowlist(self) -> list[str]:
        """Config list wins; else the env var; else empty -> fail closed."""
        if self._allowlist_cfg is not None:
            return [str(c) for c in self._allowlist_cfg]
        raw = os.environ.get(ALLOWLIST_ENV, "")
        return [c.strip() for c in raw.split(",") if c.strip()]

    def _fail(self, status: str, reason: str, **kw) -> Result:
        """Canonical degraded shape: warnings always carry
        '<status>: <reason>' so every surface reads the same sentence."""
        return fail(status, warnings=[f"{status}: {reason}"], **kw)

    def _journal_task(
        self,
        *,
        event_id: str,
        task_id: str,
        state: str,
        summary: str,
        payload: dict[str, Any],
        correlation_id: str | None,
    ) -> None:
        """ADR-0006: one TASK row on the existing append-only journal —
        not a new bus or store. ts/kind/provenance.source carry the
        envelope's timestamp/subject-type/source; the durable fields are
        event_id/task_id/state/correlation_id; transport stays out."""
        if self.journal is None:  # guarded by run_task; belt and braces
            return
        self.journal.append(
            JournalEvent(
                kind=JournalKind.TASK,
                summary=summary,
                provenance=Provenance(source="workbench", provider="podman"),
                event_id=event_id,
                task_id=task_id,
                state=state,
                payload=payload,
                correlation_id=correlation_id,
            )
        )

    def _journal_security(self, summary: str) -> None:
        """Refusals are security-relevant: audit them when a journal is
        wired (a refusal without a journal means nothing ran anyway)."""
        if self.journal is None:
            return
        self.journal.append(
            JournalEvent(
                kind=JournalKind.SECURITY,
                summary=summary,
                provenance=Provenance(source="workbench", provider="podman"),
            )
        )

    # ── capability surface ──────────────────────────────────────────

    def observe(self) -> Result:
        """status: not_configured when off, unavailable when
        podman cannot answer, healthy with the real environment list
        otherwise. Never a fabricated list."""
        if not self.enabled():
            return self._fail(
                Status.NOT_CONFIGURED.value,
                f"workbench is off — set {WORKBENCH_ENV}=1 to enable",
                actions=["list_environments", "run_task"],
            )
        if self._binary() is None:
            return self._fail(
                Status.UNAVAILABLE.value,
                f"'{self.podman_bin}' not found on PATH",
                actions=["list_environments", "run_task"],
            )
        envs = self.list_environments()
        data: dict[str, Any] = {
            "provider": "workbench",
            "impl": "podman",
            "allowed_containers": self.allowlist(),
        }
        warnings: list[str] = []
        if not envs.ok:
            return fail(
                envs.status,
                warnings=envs.warnings + ["actions: list_environments, run_task"],
            )
        data["environments"] = envs.data["environments"]
        if not self.allowlist():
            warnings.append(
                "unavailable for tasks: allowlist is empty, run_task "
                "refuses every container (fail closed)"
            )
        return ok(
            "healthy",
            data=data,
            warnings=warnings,
            actions=["list_environments", "run_task"],
        )

    def list_environments(self) -> Result:
        """Read-only enumeration via `podman ps --format json`.
        Any error degrades to 'unavailable: <reason>' — never a fake
        or partial list presented as the truth."""
        if not self.enabled():
            return self._fail(
                Status.NOT_CONFIGURED.value,
                f"workbench is off — set {WORKBENCH_ENV}=1 to enable",
            )
        binary = self._binary()
        if binary is None:
            return self._fail(
                "unavailable", f"'{self.podman_bin}' not found on PATH"
            )
        try:
            proc = subprocess.run(  # nosec B603  # argument list, no shell; `binary` was resolved with shutil.which
                [binary, "ps", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=self.default_timeout,
                env=dict(self.exec_env),
                check=True,
            )
        except subprocess.TimeoutExpired:
            return self._fail("unavailable", "'podman ps' timed out")
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or "").strip()[:200] or f"exit {e.returncode}"
            return self._fail("unavailable", f"'podman ps' failed: {detail}")
        except OSError as e:
            return self._fail("unavailable", f"cannot run '{self.podman_bin}': {e}")
        try:
            raw = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError as e:
            return self._fail("unavailable", f"'podman ps' returned unparseable JSON: {e}")
        if not isinstance(raw, list):
            return self._fail("unavailable", "'podman ps' returned unexpected JSON shape")
        environments = []
        for c in raw:
            if not isinstance(c, dict):
                continue
            names = c.get("Names")
            name = names[0] if isinstance(names, list) and names else names
            environments.append(
                {
                    # missing fields stay None — never invented
                    "name": name,
                    "id": (c.get("Id") or "")[:12] or None,
                    "image": c.get("Image"),
                    "status": c.get("State") or c.get("Status"),
                }
            )
        return ok(
            "healthy",
            data={"environments": environments, "count": len(environments)},
        )

    def run_task(
        self,
        container: str,
        argv: Any,
        *,
        timeout: float | None = None,
        correlation_id: str | None = None,
    ) -> Result:
        """Execute a bounded argv inside an allowlisted container:
        `podman exec <container> <argv...>` — argv never touches a
        shell. Returns captured stdout/stderr/exit and records one TASK
        journal event per execution attempt that reached the executor
        (refusals are SECURITY events instead)."""
        task_id = f"task-{uuid.uuid4()}"
        event_id = str(uuid.uuid4())
        label = f"task {task_id} ({container})"

        # ── security minimum, evaluated before anything is launched ──
        if not self.enabled():
            self._journal_security(
                f"workbench run_task refused: {WORKBENCH_ENV} not set ({label})"
            )
            return self._fail(
                Status.NOT_CONFIGURED.value,
                f"workbench is off — set {WORKBENCH_ENV}=1 to enable",
            )
        if not isinstance(container, str) or not _CONTAINER_RE.match(container or ""):
            self._journal_security(
                f"workbench run_task refused: invalid container name {container!r} ({label})"
            )
            return self._fail(
                "denied",
                "container name must match ^[A-Za-z0-9][A-Za-z0-9_.-]*$ "
                "(no shell metacharacters, no option-injection leading dash)",
            )
        if container not in self.allowlist():
            self._journal_security(
                f"workbench run_task refused: container '{container}' is not "
                f"in the allowlist {self.allowlist()} ({label})"
            )
            return self._fail(
                "denied",
                f"container '{container}' is not in the workbench allowlist "
                "(empty allowlist allows nothing — fail closed)",
            )
        if (
            not isinstance(argv, (list, tuple))
            or not argv
            or not all(isinstance(a, str) and "\x00" not in a for a in argv)
        ):
            self._journal_security(
                f"workbench run_task refused: argv {argv!r} is not a bounded "
                f"string list for container '{container}' ({label})"
            )
            return self._fail(
                "denied",
                "argv must be a non-empty list of strings — shell strings "
                "are refused (argv never touches a shell)",
            )
        if self.journal is None:
            return self._fail(
                Status.UNAVAILABLE.value,
                "no journal wired: run_task refuses to execute unaudited work",
            )
        binary = self._binary()
        if binary is None:
            return self._fail(
                "unavailable", f"'{self.podman_bin}' not found on PATH"
            )

        budget = self._clamp(timeout) if timeout else self.default_timeout
        cmd = [binary, "exec", container, *argv]
        started = now().isoformat()
        stdout = stderr = ""
        exit_code: int | None = None
        state = "completed"
        try:
            # env=dict(self.exec_env) — explicitly empty by default.
            # No shell=True anywhere, ever.
            proc = subprocess.run(  # nosec B603  # argument list, no shell (never shell=True); each part is allow-listed above
                cmd,
                capture_output=True,
                text=True,
                timeout=budget,
                env=dict(self.exec_env),
            )  # check=False: a non-zero exit is data, not an exception
            exit_code = proc.returncode
            stdout, stderr = proc.stdout or "", proc.stderr or ""
            if exit_code != 0:
                state = "failed"
        except subprocess.TimeoutExpired as e:
            state = "timeout"
            stdout = _as_text(e.stdout)
            stderr = (_as_text(e.stderr) + f"\nkilled after {budget}s timeout").strip()
        except OSError as e:
            # exec itself failed (binary vanished, fork limits): nothing
            # verifiably ran, so no TASK claim is recorded — error only.
            return self._fail("unavailable", f"cannot launch '{self.podman_bin}': {e}")

        finished = now().isoformat()
        stdout_truncated = len(stdout) > STDOUT_CAP
        stderr_truncated = len(stderr) > STDERR_CAP
        payload = {
            "container": container,
            "argv": list(argv),
            "exit_code": exit_code,
            "timeout_s": budget,
            "started_at": started,
            "finished_at": finished,
            "stdout_tail": stdout[-STDOUT_CAP:],
            "stderr_tail": stderr[-STDERR_CAP:],
        }
        summary = (
            f"workbench {state}: {container} argv={list(argv)!r} "
            f"exit={exit_code} task_id={task_id}"
        )
        self._journal_task(
            event_id=event_id,
            task_id=task_id,
            state=state,
            summary=summary,
            payload=payload,
            correlation_id=correlation_id,
        )
        data = {
            "task_id": task_id,
            "event_id": event_id,
            "correlation_id": correlation_id,
            "container": container,
            "argv": list(argv),
            "exit_code": exit_code,
            "stdout": stdout[:STDOUT_CAP],
            "stderr": stderr[:STDERR_CAP],
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "state": state,
        }
        if state == "completed":
            return ok(state, data=data)
        if state == "failed":
            return fail(state, warnings=[f"failed: exit {exit_code}"], data=data)
        return fail(
            state, warnings=[f"timeout: killed after {budget}s"], data=data
        )


def _as_text(chunk: Any) -> str:
    """TimeoutExpired carries bytes-or-str depending on mode; never let
    the decode itself turn a timeout into a crash."""
    if isinstance(chunk, bytes):
        return chunk.decode("utf-8", errors="replace")
    return chunk or ""
