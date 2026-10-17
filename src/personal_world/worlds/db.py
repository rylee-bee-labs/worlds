"""worlds.db: the one SQLite database (C3, C4, sessions, agent tokens).

WAL, synchronous=FULL, foreign keys on, a busy timeout, and ``BEGIN IMMEDIATE`` for every write
transaction (use :func:`write_tx`). One connection per thread; tables are created by ordered,
idempotent migrations recorded in ``schema_migrations``.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_NAME = "worlds.db"

_MIGRATIONS: list[tuple[int, str]] = []
_extra: dict[str, list[tuple[int, str]]] = {}


def register_migrations(owner: str, migrations: list[tuple[int, str]]) -> None:
    """Modules register their schema here (``owner`` namespaces the version numbers)."""
    _extra[owner] = migrations


def _create_private_file(path: os.PathLike[str]) -> bool:
    """Create ``path`` mode 0600 if it is absent; return whether this call created it.

    SQLite creates a new database with the process umask, which every thread shares: flipping
    it around the connect would silently change what other threads create. Creating the file
    first, privately, means it is never born group/other-readable and no global state moves.
    """
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "wb") as fh:
        os.fchmod(fh.fileno(), 0o600)   # the requested mode is still masked by the caller's umask
    return True


class Database:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.path.parent, 0o700)   # also when the directory already existed with looser bits
        except OSError:
            pass
        self._local = threading.local()
        self._conns: list[sqlite3.Connection] = []
        self._lock = threading.Lock()
        self._migrate()
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @classmethod
    def in_dir(cls, data_dir: str | os.PathLike[str]) -> "Database":
        return cls(Path(data_dir) / DB_NAME)

    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            created = _create_private_file(self.path)   # the db is born private, without touching the process umask
            try:
                c = sqlite3.connect(self.path, isolation_level=None, timeout=10, check_same_thread=False)
            except BaseException:
                if created:
                    self.path.unlink(missing_ok=True)   # no half-created file left behind
                raise
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=FULL")
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA trusted_schema=OFF")  # a restored/foreign database cannot run functions from its schema
            c.execute("PRAGMA busy_timeout=10000")
            self._local.conn = c
            with self._lock:
                self._conns.append(c)
            self._tighten()
        return c

    def _tighten(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.chmod(f"{self.path}{suffix}", 0o600)
            except OSError:
                pass

    @contextmanager
    def write_tx(self) -> Iterator[sqlite3.Connection]:
        """``BEGIN IMMEDIATE`` ... commit, or rollback on any exception."""
        c = self.conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
        except BaseException:
            c.execute("ROLLBACK")
            raise
        else:
            c.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            for c in self._conns:
                try:
                    c.close()
                except sqlite3.Error:
                    pass
            self._conns.clear()
        self._local = threading.local()

    def _migrate(self) -> None:
        import importlib

        for mod in ("authn", "dispatcher", "memory_store"):  # modules that register schema on import
            try:
                importlib.import_module(f"personal_world.worlds.{mod}")
            except ModuleNotFoundError as exc:
                if exc.name != f"personal_world.worlds.{mod}":
                    raise
        c = self.conn()
        c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (owner TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY(owner, version))")
        for owner, migrations in sorted(_extra.items()):
            done = {r["version"] for r in c.execute("SELECT version FROM schema_migrations WHERE owner=?", (owner,))}
            for version, sql in sorted(migrations):
                if version in done:
                    continue
                with self.write_tx() as tx:
                    for stmt in [s for s in sql.split(";\n") if s.strip()]:
                        tx.execute(stmt)
                    tx.execute("INSERT INTO schema_migrations(owner, version) VALUES (?,?)", (owner, version))
