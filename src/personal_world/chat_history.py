"""Per-principal chat history: append-only NDJSON, one file per person.

Decision #13 (multi-user): chat/history is per-user state. The file is
resolved through ``identity.principal_scoped_path(..., "chat_history")``
so the single-user default keeps one legacy file at
``<data_dir>/chat-history.ndjson`` and each multi-mode person gets their
own tree copy. This is a transcript, not a journal: the journal is the
world's audit event stream, while this is conversational memory for the
chat surface (and a future sync-friendly artifact — decision #15).

Entries never contain credentials; content is capped so a runaway model
reply cannot grow the file without bound.
"""

import json
import time
from pathlib import Path
from typing import Any

MAX_CONTENT_CHARS = 4000


class ChatHistory:
    """Append-only NDJSON transcript bound to one path."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(
        self,
        role: str,
        content: str,
        provider: str | None = None,
    ) -> dict[str, Any] | None:
        """Append one transcript line. Empty content is skipped."""
        if not content:
            return None
        entry: dict[str, Any] = {
            "ts": time.time(),
            "role": role,
            "content": str(content)[:MAX_CONTENT_CHARS],
        }
        if provider:
            entry["provider"] = provider
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def entries(self) -> list[dict[str, Any]]:
        """All transcript entries, oldest first. Malformed lines are
        skipped, never fatal (a corrupt line must not erase history)."""
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue
                if isinstance(parsed, dict):
                    out.append(parsed)
        return out

    def recent(self, n: int = 50) -> list[dict[str, Any]]:
        """The newest ``n`` entries, oldest first."""
        return self.entries()[-max(int(n), 0) :]
