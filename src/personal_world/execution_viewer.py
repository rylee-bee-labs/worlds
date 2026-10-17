"""Execution Viewer: structured records of bounded command/process executions.

Captures executions from native providers, agents, and approved actions.
NOT an arbitrary shell executor — records what already happened.

Each execution record contains:
- id: unique execution ID
- actor: who/what triggered it (provider name, agent id, "owner", "brain")
- target: what was acted upon (service name, repo, capability)
- host/runtime: where it ran (local, container name, remote host)
- command/operation: what was done (the actual command or operation name)
- timestamps: started_at, completed_at
- status: running/completed/failed/cancelled
- exit_code: process exit code (null if not a process)
- stdout/stderr: captured output (truncated for safety)
- provenance: source, authority, evidence
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ExecutionRecord:
    """A bounded execution record."""
    id: str
    actor: str
    target: str
    host: str
    command: str
    started_at: str
    completed_at: str | None = None
    status: str = "running"  # running/completed/failed/cancelled
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_summary(self) -> dict[str, Any]:
        """Compact summary (no stdout/stderr)."""
        return {
            "id": self.id,
            "actor": self.actor,
            "target": self.target,
            "command": self.command,
            "status": self.status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class ExecutionStore:
    """Persistent storage for execution records."""

    def __init__(self, data_dir: Path):
        self._path = data_dir / "executions.json"
        self._records: list[dict[str, Any]] = []
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                self._records = json.loads(self._path.read_text())
            except Exception:
                self._records = []

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Keep last 1000 records
        self._records = self._records[-1000:]
        self._path.write_text(json.dumps(self._records, indent=2))

    def append(self, record: ExecutionRecord):
        self._records.append(record.to_dict())
        self._save()

    def update(self, record_id: str, **updates):
        for r in self._records:
            if r.get("id") == record_id:
                r.update(updates)
                self._save()
                return

    def query(self, actor=None, target=None, status=None, limit=50) -> list[dict[str, Any]]:
        """Query execution records."""
        results = self._records
        if actor:
            results = [r for r in results if r.get("actor") == actor]
        if target:
            results = [r for r in results if r.get("target") == target]
        if status:
            results = [r for r in results if r.get("status") == status]
        return results[-limit:]

    def get(self, record_id: str) -> dict[str, Any] | None:
        for r in self._records:
            if r.get("id") == record_id:
                return r
        return None


class ExecutionViewer:
    """Records and queries bounded executions."""

    def __init__(self, data_dir: Path):
        self.store = ExecutionStore(data_dir)

    def record_execution(
        self,
        actor: str,
        target: str,
        command: str,
        host: str = "local",
        provenance: dict[str, Any] | None = None,
    ) -> ExecutionRecord:
        """Start recording an execution."""
        record = ExecutionRecord(
            id=str(uuid.uuid4())[:8],
            actor=actor,
            target=target,
            host=host,
            command=command,
            started_at=datetime.now(timezone.utc).isoformat(),
            provenance=provenance or {"source": "execution_viewer"},
        )
        self.store.append(record)
        return record

    def complete_execution(
        self,
        record_id: str,
        exit_code: int = 0,
        stdout: str | None = None,
        stderr: str | None = None,
        status: str = "completed",
    ):
        """Mark an execution as complete."""
        self.store.update(
            record_id,
            completed_at=datetime.now(timezone.utc).isoformat(),
            status=status,
            exit_code=exit_code,
            stdout=(stdout[:10000] if stdout else None),  # Truncate for safety
            stderr=(stderr[:10000] if stderr else None),
        )

    def fail_execution(self, record_id: str, error: str, exit_code: int = 1):
        """Mark an execution as failed."""
        self.complete_execution(record_id, exit_code=exit_code, stderr=error, status="failed")

    def recent(self, limit=20) -> list[dict[str, Any]]:
        """Get recent executions."""
        return self.store.query(limit=limit)

    def by_actor(self, actor: str, limit=20) -> list[dict[str, Any]]:
        """Get executions by actor."""
        return self.store.query(actor=actor, limit=limit)

    def by_target(self, target: str, limit=20) -> list[dict[str, Any]]:
        """Get executions by target."""
        return self.store.query(target=target, limit=limit)

    def observe(self) -> dict[str, Any]:
        """Report execution viewer status."""
        total = len(self.store._records)
        recent = self.store.query(limit=5)
        return {
            "total_executions": total,
            "recent": [r.get("id") for r in recent],
            "provider": "execution_viewer",
        }
