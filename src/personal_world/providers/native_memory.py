"""Native Memory provider: SQLite FTS5 disposable index over journal/notes.

Markdown/files remain canonical truth. SQLite FTS5 is the search/index
implementation. The index is rebuildable and disposable. No Qdrant,
Chroma, Postgres, vector database, or embedding server required.
"""

import sqlite3
from pathlib import Path

from ..envelope import Result, fail, ok
from ..status import Status
from .registry import Contract


class NativeMemoryProvider(Contract):
    """Native memory capability using SQLite FTS5."""

    def __init__(self, data_dir: Path, journal=None):
        self._db_path = data_dir / "memory.fts5.db"
        self._journal = journal
        self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory
                USING fts5(
                    id,
                    kind,
                    text,
                    timestamp UNINDEXED
                )
            """)
            self._conn.commit()
        return self._conn

    def index_journal(self) -> int:
        """Index journal entries. Returns count indexed."""
        if self._journal is None:
            return 0
        conn = self._get_conn()
        events = self._journal.recent(1000) if hasattr(self._journal, 'recent') else []
        count = 0
        for e in events:
            ts = e.ts.isoformat() if hasattr(e, 'ts') else str(e.ts)
            kind = e.kind.value if hasattr(e, 'kind') else str(e.kind)
            text = e.summary if hasattr(e, 'summary') else str(e)
            entry_id = f"journal:{ts}"
            conn.execute(
                "INSERT OR REPLACE INTO memory (id, kind, text, timestamp) VALUES (?, ?, ?, ?)",
                (entry_id, kind, text, ts)
            )
            count += 1
        conn.commit()
        return count

    def search(self, query: str, limit: int = 10) -> Result:
        """Search indexed memory."""
        try:
            conn = self._get_conn()
            cursor = conn.execute("SELECT COUNT(*) FROM memory")
            if cursor.fetchone()[0] == 0:
                self.index_journal()
            cursor = conn.execute(
                "SELECT id, kind, text, timestamp FROM memory WHERE memory MATCH ? ORDER BY rank LIMIT ?",
                (query, limit)
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "kind": row[1],
                    "text": row[2],
                    "timestamp": row[3],
                })
            return ok(Status.HEALTHY.value, data={
                "results": results,
                "query": query,
                "count": len(results),
            })
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"memory search: {e}"])

    def observe(self) -> Result:
        """Report memory capability status."""
        try:
            conn = self._get_conn()
            cursor = conn.execute("SELECT COUNT(*) FROM memory")
            count = cursor.fetchone()[0]
            return ok(Status.HEALTHY.value, data={
                "indexed": count,
                "provider": "native_memory",
                "backend": "sqlite_fts5",
            })
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"memory: {e}"])

    def health(self) -> bool:
        return True
