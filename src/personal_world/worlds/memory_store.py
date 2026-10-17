"""C4 memory: Kept, Later, Records, History and the Find index.

One store, four tables and one FTS5 index, in the same SQLite file as sessions and receipts
(C3). The rules that shape it:

* **The index is part of the write.** A row, its ``find_index`` entry and its ``history``
  entry are written in the *same* transaction, so a row can never be searchable without
  being counted, or counted without being there. The index has no SQL triggers: Python
  writes it, so one rollback takes all three back.
* **History is append-only.** Triggers refuse UPDATE and DELETE on ``history``; the store
  only appends. An ``updated`` event names the fields that changed and nothing else, so no
  title and no body ever reaches the audit log.
* **Locked records are a step-up gate, not a filter.** A ``records`` row with
  ``sensitivity='locked'`` raises :class:`Locked` from get/update/delete unless the caller
  steps up; listings mask it; find excludes it *in SQL*; export omits it; an agent answer
  never counts it. Locking or unlocking a row needs step-up as well, because it changes who
  can read it.
* **Find speaks words, never syntax.** The query is tokenised here, every token is quoted
  and only the last one gets a prefix ``*``; the result is bound as a parameter. Nothing a
  caller types can reach ``MATCH`` as syntax.
* **Agent access is three counts.** ``later.count``, ``kept.count``, ``records.count``, each
  needing its scope, each logged as ``agent_read``. There is no agent search.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator

from .db import Database, register_migrations

__all__ = ["MemoryStore", "MemoryError_", "NotFound", "Locked", "NotPermitted_", "restore_backup"]

register_migrations("memory", [
    (1, """CREATE TABLE kept (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]',
    provenance TEXT NOT NULL, source_ref TEXT,
    created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE later (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', due_at REAL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','done','dropped')),
    provenance TEXT NOT NULL, source_ref TEXT,
    created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE records (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', kind TEXT,
    sensitivity TEXT NOT NULL DEFAULT 'normal' CHECK (sensitivity IN ('normal','locked')),
    provenance TEXT NOT NULL, source_ref TEXT,
    created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, actor TEXT NOT NULL, event TEXT NOT NULL,
    table_name TEXT, row_id TEXT, detail TEXT);
CREATE TRIGGER history_no_update BEFORE UPDATE ON history BEGIN SELECT RAISE(ABORT, 'history is append-only'); END;
CREATE TRIGGER history_no_delete BEFORE DELETE ON history BEGIN SELECT RAISE(ABORT, 'history is append-only'); END;
CREATE VIRTUAL TABLE find_index USING fts5(
    table_name UNINDEXED, row_id UNINDEXED, sensitivity UNINDEXED, title, body,
    tokenize='unicode61 remove_diacritics 2')"""),
])

#: The three memory tables. Every table name in SQL comes from this tuple, never from a caller.
TABLES: tuple[str, ...] = ("kept", "later", "records")
PROVENANCES: tuple[str, ...] = ("owner", "suggestion", "external_ref")
STATUSES: tuple[str, ...] = ("open", "done", "dropped")
SENSITIVITIES: tuple[str, ...] = ("normal", "locked")

#: The fields each table has. ``add`` fills them all in, ``update`` may touch only these.
_FIELDS: dict[str, tuple[str, ...]] = {
    "kept": ("title", "body", "tags"),
    "later": ("title", "body", "due_at", "status"),
    "records": ("title", "body", "kind", "sensitivity"),
}
#: The store's own bookkeeping: a caller can read these, never set them.
_IMMUTABLE: tuple[str, ...] = ("id", "table", "provenance", "source_ref", "created_at", "updated_at")

_MAX_LIST = 500
_MAX_HISTORY = 500
_MAX_FIND_LIMIT = 100
_MAX_TITLE = 200
_MAX_BODY = 65536
_MAX_TAGS = 32
_MAX_TAG_LEN = 64
_MAX_KIND_LEN = 64
_MAX_SOURCE_REF = 512
_MAX_TERMS = 12
_MAX_TERM_LEN = 64
#: A restored history row's text is only ever displayed: it is bounded like any other stored text.
_MAX_HISTORY_ACTOR = 200
_MAX_HISTORY_EVENT = 200

#: find tokenises on letters and digits of any script; everything else is dropped.
_WORDS = re.compile(r"[^\W_]+", re.UNICODE)
#: FTS5 snippet marker, only used to see which column the match landed in.
_MARK = "«"
#: SQLite's PRIMARY KEY / UNIQUE refusal names the table and the ``id`` column; that is a duplicate id.
_DUPLICATE_ID = re.compile(r"UNIQUE constraint failed: \w+\.id\b")


class MemoryError_(Exception):
    """The row as asked for is not a row this store will write."""


class NotFound(Exception):
    """No such row (or no such agent answer name)."""


class Locked(Exception):
    """The row is a locked record and the caller has not stepped up."""


class NotPermitted_(Exception):
    """The caller's scopes do not cover what was asked for."""


# ------------------------------------------------------------------ validation


def _require_table(table: str, allowed: tuple[str, ...] = TABLES) -> str:
    if not isinstance(table, str) or table not in allowed:
        raise MemoryError_(f"unknown table {table!r}")
    return table


def _text(value: Any, field: str, max_len: int) -> str:
    if not isinstance(value, str):
        raise MemoryError_(f"{field} must be a string")
    if len(value) > max_len:
        raise MemoryError_(f"{field} may be at most {max_len} characters")
    return value


def _page(limit: Any, maximum: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
        raise MemoryError_(f"limit must be between 1 and {maximum}")
    return limit


def _one_of(value: Any, field: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise MemoryError_(f"{field} must be one of {'|'.join(allowed)}")
    return value


def _field_value(table: str, field: str, value: Any) -> Any:
    """Validate one field for ``table`` and return it normalised.

    A field the table does not have is a mistake in the call, not a value to store: it is
    refused, so ``add("kept", sensitivity="locked")`` cannot quietly become a no-op.
    """
    if field in _IMMUTABLE:
        raise MemoryError_(f"{field} cannot be set")
    if field not in _FIELDS[table]:
        raise MemoryError_(f"{table} has no field {field!r}")
    if field == "title":
        title = _text(value, "title", _MAX_TITLE).strip()
        if not title:
            raise MemoryError_("title must not be empty")
        return title
    if field == "body":
        return _text(value, "body", _MAX_BODY)
    if field == "tags":
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            raise MemoryError_("tags must be a list of strings")
        if len(value) > _MAX_TAGS:
            raise MemoryError_(f"at most {_MAX_TAGS} tags")
        return [_text(tag, "tag", _MAX_TAG_LEN) for tag in value]
    if field == "kind":
        if value is None:
            return None
        return _text(value, "kind", _MAX_KIND_LEN)
    if field == "sensitivity":
        return _one_of(value, "sensitivity", SENSITIVITIES)
    if field == "status":
        return _one_of(value, "status", STATUSES)
    if field == "due_at":  # the only numeric one
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MemoryError_("due_at must be a number or None")
        return float(value)
    raise MemoryError_(f"{table} has no field {field!r}")  # pragma: no cover - _FIELDS is closed


def _provenance(provenance: Any, source_ref: Any) -> tuple[str, str | None]:
    """``external_ref`` is the only provenance that may point somewhere; the rest may not."""
    provenance = _one_of(provenance, "provenance", PROVENANCES)
    if provenance == "external_ref":
        if not isinstance(source_ref, str) or not source_ref.strip():
            raise MemoryError_("external_ref needs a source_ref")
        return provenance, _text(source_ref, "source_ref", _MAX_SOURCE_REF)
    if source_ref not in (None, ""):
        raise MemoryError_("only external_ref may carry a source_ref")
    return provenance, None


def _actor(actor: Any) -> str:
    if not isinstance(actor, str) or not actor.strip():
        raise MemoryError_("an actor is required")
    return actor


def _history_text(value: Any, field: str, max_len: int) -> str:
    """A restored history field is opaque display text: non-empty, bounded, never parsed.

    It is not an identity, a scope or a grant, so no actor list is consulted and no permission is
    derived from it; :meth:`MemoryStore.history` is the only thing that reads it back.
    """
    if not isinstance(value, str) or not value.strip():
        raise MemoryError_(f"history {field} must be a non-empty string")
    return _text(value, f"history {field}", max_len)


def _scope_ok(needed: str, granted: Any) -> bool:
    for scope in granted or ():
        if not isinstance(scope, str):
            continue
        if scope in (needed, "*"):
            return True
        if scope.endswith(".*") and needed.startswith(scope[:-1]):
            return True
    return False


class MemoryStore:
    """Kept, Later and Records with their history, their find index and their export."""

    #: The only things an agent may ask for. Each one is a count, each one is scoped.
    AGENT_ANSWERS: dict[str, str] = {
        "later.count": "SELECT count(*) FROM later WHERE status='open'",
        "kept.count": "SELECT count(*) FROM kept",
        "records.count": "SELECT count(*) FROM records WHERE sensitivity != 'locked'",
    }

    def __init__(self, db: Database, clock: Callable[[], float] = time.time):
        self.db = db
        self.clock = clock
        self.dir = Path(db.path).parent

    # ------------------------------------------------------------------- write

    def add(self, table: str, *, title: str, body: str = "", actor: str,
            provenance: str = "owner", source_ref: str | None = None, tags: Any = None,
            due_at: Any = None, kind: str | None = None, sensitivity: str = "normal") -> dict:
        _require_table(table)
        actor = _actor(actor)
        values: dict[str, Any] = {}
        given = {"title": title, "body": body, "tags": tags, "due_at": due_at, "kind": kind,
                 "sensitivity": sensitivity, "status": "open"}   # a new later row is always open
        for field in _FIELDS[table]:
            values[field] = _field_value(table, field, given[field])
        values["provenance"], values["source_ref"] = _provenance(provenance, source_ref)
        now = float(self.clock())
        row_id = uuid.uuid4().hex
        values.update(id=row_id, created_at=now, updated_at=now)
        with self.db.write_tx() as tx:
            self._insert(tx, table, values)
            self._index(tx, table, row_id, values["title"], values["body"], values.get("sensitivity", "normal"))
            self._record_history(tx, "created", table, row_id, None, actor=actor)
        return self._out(table, values)

    def update(self, table: str, id: str, fields: dict, *, actor: str, step_up: bool = False) -> dict:
        _require_table(table)
        actor = _actor(actor)
        if not isinstance(fields, dict) or not fields:
            raise MemoryError_("an update needs at least one field")
        clean = {name: _field_value(table, name, value) for name, value in fields.items()}
        now = float(self.clock())
        with self.db.write_tx() as tx:
            # The gates run INSIDE the write transaction (BEGIN IMMEDIATE): what is checked is what is written.
            current = self._out(table, self._fetch(table, id, tx))
            self._gate_locked(current, step_up)
            # Locking hides a record, unlocking reveals it. Both change who can read it.
            if "sensitivity" in clean and clean["sensitivity"] != current.get("sensitivity") and not step_up:
                raise Locked("changing sensitivity needs step-up")
            merged = {**current, **clean, "updated_at": now}
            tx.execute(f"UPDATE {table} SET {', '.join(f'{n}=?' for n in [*clean])}, updated_at=? WHERE id=?",  # nosec B608  # {table} is allowlisted by _require_table and every column name by _field_value
                       [self._encode(n, v) for n, v in clean.items()] + [now, id])
            tx.execute("DELETE FROM find_index WHERE row_id=?", (id,))
            self._index(tx, table, id, merged["title"], merged["body"], merged.get("sensitivity", "normal"))
            self._record_history(tx, "updated", table, id, {"fields": sorted(clean)}, actor=actor)
        return merged

    @staticmethod
    def _gate_locked(row: dict, step_up: bool) -> None:
        """THE locked-record gate: a locked row is readable, editable and removable only under step-up."""
        if row.get("sensitivity") == "locked" and step_up is not True:
            raise Locked("this record is locked; step up first")

    def delete(self, table: str, id: str, *, actor: str, step_up: bool = False) -> None:
        _require_table(table)
        actor = _actor(actor)
        with self.db.write_tx() as tx:
            self._gate_locked(self._out(table, self._fetch(table, id, tx)), step_up)
            tx.execute(f"DELETE FROM {table} WHERE id=?", (id,))  # nosec B608  # {table} is allowlisted by _require_table
            tx.execute("DELETE FROM find_index WHERE row_id=?", (id,))
            self._record_history(tx, "deleted", table, id, None, actor=actor)

    # -------------------------------------------------------------------- read

    def get(self, table: str, id: str, *, step_up: bool = False, actor: str = "owner") -> dict:
        _require_table(table)
        row = self._out(table, self._fetch(table, id))
        self._gate_locked(row, step_up)
        if row.get("sensitivity") == "locked":
            self._log("read_locked", table, row["id"], None, actor=_actor(actor))
        return row

    def list(self, table: str, *, step_up: bool = False, status: str | None = None,
             limit: int = 50, offset: int = 0) -> list[dict]:
        _require_table(table)
        limit = _page(limit, _MAX_LIST)
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise MemoryError_("offset must be 0 or more")
        if status is not None and (table != "later" or status not in STATUSES):
            raise MemoryError_("only later rows have a status")
        where = " WHERE status=?" if status is not None else ""
        order = "(due_at IS NULL), due_at, created_at DESC, rowid DESC" if table == "later" \
            else "created_at DESC, rowid DESC"
        rows = self.db.conn().execute(
            f"SELECT * FROM {table}{where} ORDER BY {order} LIMIT ? OFFSET ?",  # nosec B608  # {table} is allowlisted by _require_table; {where}/{order} are literals
            ((status,) if status is not None else ()) + (limit, offset),
        ).fetchall()
        out = []
        for row in rows:
            item = self._out(table, row)
            if item.get("sensitivity") == "locked" and not step_up:
                out.append({"id": item["id"], "table": table, "sensitivity": "locked",
                            "locked": True, "created_at": item["created_at"]})
            else:
                out.append(item)
        return out

    def find(self, query: str, *, step_up: bool = False, agent: bool = False, limit: int = 20) -> list[dict]:
        """Search title and body. A locked record only appears for the owner, under step-up."""
        limit = _page(limit, _MAX_FIND_LIMIT)
        terms = self._terms(query)
        if terms is None:
            return []
        sql = ("SELECT table_name, row_id, sensitivity, title, "
               "snippet(find_index, 3, '«', '»', '…', 12) AS in_title, "
               "snippet(find_index, 4, '«', '»', '…', 12) AS in_body "
               "FROM find_index WHERE find_index MATCH ?")
        if not (step_up and not agent):   # excluded in SQL: a masked row never reaches the caller
            sql += " AND sensitivity != 'locked'"
        rows = self.db.conn().execute(sql + " ORDER BY rank LIMIT ?", (terms, limit)).fetchall()
        return [{"table": r["table_name"], "id": r["row_id"], "title": r["title"],
                 "snippet": self._snippet(r["in_title"], r["in_body"]),
                 "sensitivity": r["sensitivity"]} for r in rows]

    def history(self, limit: int = 50, before_id: int | None = None) -> list[dict]:
        """The append-only log, newest first. Never holds a title or a body."""
        limit = _page(limit, _MAX_HISTORY)
        where = " WHERE id < ?" if before_id is not None else ""
        rows = self.db.conn().execute(
            f"SELECT * FROM history{where} ORDER BY id DESC LIMIT ?",  # nosec B608  # {where} is one of two literals
            ((before_id,) if before_id is not None else ()) + (limit,),
        ).fetchall()
        return [self._history_out(r) for r in rows]

    def agent_answer(self, name: str, *, scopes: Any, actor: str) -> dict:
        """The only agent-facing read: a named count, if the token carries the scope."""
        sql = self.AGENT_ANSWERS.get(name) if isinstance(name, str) else None
        if sql is None:
            raise NotFound(f"there is no agent answer named {name!r}")
        if not _scope_ok(f"memory.{name}", scopes):
            raise NotPermitted_(f"an agent token needs memory.{name} for this")
        value = int(self.db.conn().execute(sql).fetchone()[0])
        self._log("agent_read", None, None, {"name": name}, actor=_actor(actor))
        return {"name": name, "value": value}

    # ------------------------------------------------------------------ export

    def export_ndjson(self, table: str, *, step_up: bool = False, actor: str = "owner") -> Iterator[str]:
        """One table as NDJSON. Locked records are left out unless the owner stepped up.

        Validated and logged when called (not when first iterated), so a refused export is refused at once.
        """
        _require_table(table, TABLES + ("history",))
        actor = _actor(actor)
        include_locked = table == "records" and step_up is True
        self._log("exported", table, None, {"locked_included": include_locked} if table == "records" else None, actor=actor)
        sql = f"SELECT * FROM {table}"  # nosec B608  # {table} is allowlisted by _require_table
        if table == "records" and not include_locked:
            sql += " WHERE sensitivity != 'locked'"
        rows = self.db.conn().execute(sql + " ORDER BY rowid").fetchall()

        def lines() -> Iterator[str]:
            for row in rows:
                item = self._history_out(row) if table == "history" else self._out(table, row)
                yield json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"

        return lines()

    # ------------------------------------------------------------------ backup

    def backup(self, dest_dir: str | os.PathLike[str], *, actor: str = "owner") -> Path:
        """A dated private copy through the online backup API, so it is consistent while writing."""
        dest = Path(dest_dir)
        _private_dir(dest)
        stamp = dt.datetime.fromtimestamp(float(self.clock()), tz=dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = dest / f"worlds-{stamp}.db"
        attempt = 0
        while path.exists():                      # never overwrite an earlier backup
            attempt += 1
            path = dest / f"worlds-{stamp}-{attempt}.db"
        # The copy is created 0600 up front, so no process umask flip is needed (that would be global):
        # it is never born group/other-readable, and its journal and the integrity check stay private.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            try:
                target = sqlite3.connect(path)
                try:
                    self.db.conn().backup(target)
                    if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise MemoryError_("the backup copy did not pass its integrity check")
                finally:
                    target.close()
            except BaseException:
                path.unlink(missing_ok=True)   # no half-written backup is left behind
                raise
            os.fchmod(fd, 0o600)   # assert on the open descriptor, never a later chmod by path
        finally:
            os.close(fd)
        self._log("backup", None, None, {"file": path.name}, actor=_actor(actor))
        return path

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _terms(query: Any) -> str | None:
        """``"annual checkup" -> '"annual" "checkup"*'``. Anything that is not a word is dropped.

        The result is a plain FTS5 string of quoted words: no column filter, no operator and
        no other syntax can survive, so the query can only ever be a conjunction of prefixes.
        """
        if not isinstance(query, str):
            return None
        words = [w.lower() for w in _WORDS.findall(query) if len(w) <= _MAX_TERM_LEN][:_MAX_TERMS]
        if not words:
            return None
        return " ".join(f'"{w}"' + ("*" if i == len(words) - 1 else "") for i, w in enumerate(words))

    @staticmethod
    def _snippet(in_title: str, in_body: str) -> str:
        """The window around the match: the body column if it matched, else the title."""
        return in_body if _MARK in in_body else in_title

    def _restore_rows(self, rows: dict[str, list[sqlite3.Row]]) -> dict:
        """Insert validated rows (and rebuild their find entries) in ONE transaction; any bad row rolls all back."""
        counts: dict[str, int] = {}
        with self.db.write_tx() as tx:
            for table in TABLES:
                for row in rows[table]:
                    values = {c: row[c] for c in _RESTORE_COLUMNS[table]}
                    self._validate_restored(table, values)
                    if table == "kept":
                        values["tags"] = json.loads(values["tags"])
                    self._insert(tx, table, values)
                    self._index(tx, table, values["id"], values["title"], values["body"], values.get("sensitivity", "normal"))
                counts[table] = len(rows[table])
            for row in rows["history"]:
                # actor and event are untrusted display text: bounded, kept opaque, never parsed or trusted.
                actor = _history_text(row["actor"], "actor", _MAX_HISTORY_ACTOR)
                event = _history_text(row["event"], "event", _MAX_HISTORY_EVENT)
                for field in ("table_name", "row_id"):
                    if row[field] is not None and not isinstance(row[field], str):
                        raise MemoryError_(f"history {field} must be a string or None")
                if row["detail"] is not None:
                    json.loads(row["detail"])   # must be valid JSON
                tx.execute("INSERT INTO history(at, actor, event, table_name, row_id, detail) VALUES (?,?,?,?,?,?)",
                           (float(row["at"]), actor, event, row["table_name"], row["row_id"], row["detail"]))
            counts["history"] = len(rows["history"])
            self._record_history(tx, "restored", None, None, {t: counts[t] for t in TABLES}, actor="owner")
        return counts

    def _validate_restored(self, table: str, values: dict) -> None:
        """A restored row must be one this store would have written (a crafted backup is refused whole)."""
        if not isinstance(values.get("id"), str) or not re.fullmatch(r"[0-9a-f]{32}", values["id"]):
            raise MemoryError_("restored row has a bad id")
        for field in _FIELDS[table]:
            raw = values[field]
            if field == "tags":
                raw = json.loads(raw)
            _field_value(table, field, raw)
        _provenance(values["provenance"], values["source_ref"])
        for stamp in ("created_at", "updated_at"):
            if isinstance(values[stamp], bool) or not isinstance(values[stamp], (int, float)):
                raise MemoryError_("restored row has a bad timestamp")

    def _fetch(self, table: str, row_id: Any, conn: sqlite3.Connection | None = None) -> sqlite3.Row:
        if not isinstance(row_id, str):
            raise NotFound("no such row")
        row = (conn or self.db.conn()).execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()  # nosec B608  # {table} is allowlisted by _require_table
        if row is None:
            raise NotFound("no such row")
        return row

    def _insert(self, tx: sqlite3.Connection, table: str, values: dict) -> None:
        columns = ", ".join(values)
        try:
            tx.execute(f"INSERT INTO {table} ({columns}) VALUES ({', '.join('?' * len(values))})",  # nosec B608  # {table}/{columns} come from the TABLES and _FIELDS constants
                       [self._encode(name, value) for name, value in values.items()])
        except sqlite3.IntegrityError as exc:
            # The row is inserted inside the caller's write transaction, so raising here rolls the
            # row, its find entry and its history entry back together. A duplicate id is the one such
            # error a caller can cause; it is named as a duplicate, and any other constraint is
            # reported truthfully, but no raw sqlite3 error ever escapes the store.
            if _DUPLICATE_ID.search(str(exc)):
                raise MemoryError_(f"{table} already has a row with this id (duplicate id)") from None
            raise MemoryError_(f"{table} refused this row: {exc}") from exc

    def _index(self, tx: sqlite3.Connection, table: str, row_id: str, title: str, body: str,
               sensitivity: str) -> None:
        """The find entry, written here rather than by a trigger so it shares the row's transaction."""
        tx.execute("INSERT INTO find_index(table_name, row_id, sensitivity, title, body) VALUES (?,?,?,?,?)",
                   (table, row_id, sensitivity if table == "records" else "normal", title, body))

    def _record_history(self, tx: sqlite3.Connection, event: str, table: str | None, row_id: str | None,
                        detail: dict | None, *, actor: str) -> None:
        """Append one history row on the caller's transaction, so a failure rolls it back too."""
        tx.execute("INSERT INTO history(at, actor, event, table_name, row_id, detail) VALUES (?,?,?,?,?,?)",
                   (float(self.clock()), actor, event, table, row_id,
                    json.dumps(detail) if detail is not None else None))

    #: Events other modules may append to History (content-free details only).
    EXTERNAL_EVENTS = ("connect_try",)

    def record_event(self, event: str, detail: dict | None, *, actor: str) -> None:
        """Append one allow-listed event written by another module (never a title or a body)."""
        if event not in self.EXTERNAL_EVENTS:
            raise MemoryError_(f"{event!r} is not an event other modules may record")
        self._log(event, None, None, detail, actor=_actor(actor))

    def _log(self, event: str, table: str | None, row_id: str | None, detail: dict | None, *, actor: str) -> None:
        with self.db.write_tx() as tx:
            self._record_history(tx, event, table, row_id, detail, actor=actor)

    @staticmethod
    def _encode(field: str, value: Any) -> Any:
        return json.dumps(value) if field == "tags" else value   # tags are stored as JSON text

    def _out(self, table: str, row: Any) -> dict:
        item = {key: row[key] for key in row.keys()}
        item["table"] = table
        if isinstance(item.get("tags"), str):   # stored as JSON, handed back as a list
            item["tags"] = json.loads(item["tags"])
        return item

    @staticmethod
    def _history_out(row: sqlite3.Row) -> dict:
        return {"id": row["id"], "at": row["at"], "actor": row["actor"], "event": row["event"],
                "table": row["table_name"], "row_id": row["row_id"],
                "detail": json.loads(row["detail"]) if row["detail"] else None}


def _private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path, 0o700)   # also when the directory already existed with looser bits
    except OSError:
        pass


_RESTORE_COLUMNS: dict[str, tuple[str, ...]] = {
    "kept": ("id", "title", "body", "tags", "provenance", "source_ref", "created_at", "updated_at"),
    "later": ("id", "title", "body", "due_at", "status", "provenance", "source_ref", "created_at", "updated_at"),
    "records": ("id", "title", "body", "kind", "sensitivity", "provenance", "source_ref", "created_at", "updated_at"),
    "history": ("at", "actor", "event", "table_name", "row_id", "detail"),
}


def restore_backup(backup_path: str | os.PathLike[str], data_dir: str | os.PathLike[str]) -> dict:
    """Restore the MEMORY rows of a backup into ``data_dir``'s current database, and nothing else.

    The backup is untrusted input. It is opened read-only with ``trusted_schema=OFF`` (no trigger or view in
    it can run), checked for integrity, and then ONLY the rows of kept, later, records and history are copied
    into a freshly migrated database in ONE transaction; every row is validated as if it were new, and the
    find index is rebuilt from the rows. A restored history row's ``actor`` and ``event`` are untrusted
    display text only: they must be non-empty strings within a sane bound, are kept opaque, and are never
    parsed, matched against a known-actor list, or used to derive trust, authority, provenance, a principal
    or any permission decision. Sessions, agent tokens, authorizations, executions, leases and every
    schema object in the backup (triggers, views, extra tables) are never imported. A target that already
    holds memory rows is refused: restore never overwrites.
    """
    source, data = Path(backup_path), Path(data_dir)
    if not source.is_file():
        raise MemoryError_(f"{source} is not a file")
    rows: dict[str, list[sqlite3.Row]] = {}
    try:
        probe = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise MemoryError_(f"{source} cannot be read as a database") from exc
    try:
        probe.row_factory = sqlite3.Row
        probe.execute("PRAGMA trusted_schema=OFF")
        names = {r[0] for r in probe.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not set(_RESTORE_COLUMNS) <= names:
            raise MemoryError_(f"{source} is not a Worlds memory database")
        if probe.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise MemoryError_(f"{source} does not pass its integrity check")
        for table, cols in _RESTORE_COLUMNS.items():
            have = {r[1] for r in probe.execute(f"PRAGMA table_info({table})")}
            if not set(cols) <= have:
                raise MemoryError_(f"{source} has an unexpected {table} table")
            rows[table] = probe.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY rowid").fetchall()  # nosec B608  # {cols} is checked against this table's own PRAGMA columns above
    except sqlite3.Error as exc:
        raise MemoryError_(f"{source} cannot be read as a database") from exc
    finally:
        probe.close()
    _private_dir(data)
    # The fresh database is born 0600 by Database itself (see _create_private_file), so restore never
    # flips the process umask; its -wal/-shm siblings inherit that mode and are tightened too.
    db = Database.in_dir(data)               # freshly migrated: the schema is ours, never the backup's
    try:
        store = MemoryStore(db)
        if any(db.conn().execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES):  # nosec B608  # {t} iterates the TABLES constant
            raise MemoryError_("this database already holds memory; restore never overwrites it")
        try:
            return store._restore_rows(rows)
        except (ValueError, TypeError, KeyError) as exc:   # a crafted row: refused whole, nothing was written
            raise MemoryError_(f"the backup holds a row this store would not write ({type(exc).__name__})") from None
    finally:
        db.close()
