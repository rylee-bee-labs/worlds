"""C1 config store: YAML files are the canonical truth (docs/rebuild/CONTRACTS.md).

Layout::

    <root>/worlds/providers/<id>.yaml
    <root>/worlds/requests/<provider>/<id>.yaml
    <root>/worlds/cards/<id>.yaml
    <root>/worlds/boards/<id>.yaml
    <root>/worlds/actions/<id>.yaml

Rules enforced here:
* yaml.safe_load / yaml.safe_dump only, schema_version must be 1, filename stem
  must equal the object id;
* ids are validated against the models' patterns *before* any path is built, so
  a crafted id can never escape the config root;
* writes are atomic (tmp file in the same directory + fsync + os.replace, then
  the directory is fsynced) and never world-writable;
* etag = sha256 of the file bytes; ``etag=""`` means "must not exist yet";
* references (request.provider, card requests, board cards, action.request) are
  validated on save, and delete is refused while anything still references the
  object;
* an invalid file keeps the last valid object active and is reported through
  :meth:`ConfigStore.errors`;
* nothing here executes anything - reload only reads and parses.

Secrets: only a ``secret_ref`` (``env:NAME`` / ``vault:NAME``) is ever stored or
logged; a secret value never enters this module.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Iterator

import yaml
from pydantic import BaseModel, ValidationError

from . import models
from .models import ID_RE, REQUEST_ID_RE, Action, Board, Card, Provider, Request

__all__ = ["ConfigStore", "ConfigInvalid", "EtagMismatch", "KINDS"]

logger = logging.getLogger(__name__)

MODEL_BY_KIND: dict[str, type[BaseModel]] = {
    "provider": Provider,
    "request": Request,
    "card": Card,
    "board": Board,
    "action": Action,
}
KINDS = tuple(MODEL_BY_KIND)

#: worlds sub-directory per kind (requests add a per-provider level below it).
_DIR_BY_KIND = {
    "provider": "providers",
    "request": "requests",
    "card": "cards",
    "board": "boards",
    "action": "actions",
}

_ID_PATTERNS = {k: ID_RE for k in KINDS}
_ID_PATTERNS["request"] = REQUEST_ID_RE

_MAX_MESSAGE = 240


class ConfigInvalid(Exception):
    """A config was refused: bad id, schema violation, or a dangling reference."""


class EtagMismatch(Exception):
    """Optimistic concurrency failed; the caller's etag is not the current one."""


def _short(message: str) -> str:
    """One-line error message. Never a traceback."""
    flat = " | ".join(part.strip() for part in str(message).splitlines() if part.strip())
    if len(flat) > _MAX_MESSAGE:
        flat = flat[: _MAX_MESSAGE - 1] + "…"
    return flat


def _describe(exc: Exception, what: str) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        loc = ".".join(str(part) for part in first.get("loc", ())) or "config"
        return f"{what}: {loc} {first.get('msg', 'is invalid')}"
    return f"{what}: {_short(exc)}"


class ConfigStore:
    """In-memory index over the YAML config files, kept in sync with disk."""

    def __init__(self, root: str | os.PathLike[str]):
        self._root = Path(root)
        self._worlds = self._root / "worlds"
        self._lock = threading.RLock()
        self._objects: dict[str, dict[str, BaseModel]] = {k: {} for k in KINDS}
        self._etags: dict[str, dict[str, str]] = {k: {} for k in KINDS}
        self._errors: list[dict[str, str]] = []
        self._versions: dict[str, str | None] = {}
        self._listeners: list[Callable[[list[str]], None]] = []
        self.reload()

    # ------------------------------------------------------------------ paths

    def _check_kind(self, kind: str) -> None:
        if kind not in MODEL_BY_KIND:
            raise ConfigInvalid(f"unknown kind: {kind!r}")

    def _check_id(self, kind: str, obj_id: Any) -> str:
        """Validate an id *before* it is used to build a path (no traversal)."""
        if not isinstance(obj_id, str) or not re.match(_ID_PATTERNS[kind], obj_id):
            raise ConfigInvalid(f"{kind} id {obj_id!r} does not match {_ID_PATTERNS[kind]}")
        return obj_id

    def _path_for(self, kind: str, obj_id: str) -> Path:
        directory = self._worlds / _DIR_BY_KIND[kind]
        if kind == "request":
            provider, sep, _ = obj_id.partition(".")
            if not sep:
                raise ConfigInvalid(f"request id {obj_id!r} must be <provider>.<name>")
            directory = directory / provider
        return directory / f"{obj_id}.yaml"

    def _files(self, kind: str) -> list[Path]:
        directory = self._worlds / _DIR_BY_KIND[kind]
        if kind == "request":
            files: list[Path] = []
            if directory.is_dir():
                for sub in sorted(p for p in directory.iterdir() if p.is_dir()):
                    files.extend(sorted(sub.glob("*.yaml")))
            return files
        return sorted(directory.glob("*.yaml")) if directory.is_dir() else []

    # -------------------------------------------------------------- loading

    def _file_etag(self, path: Path) -> str | None:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return None

    def _rel(self, path: Path) -> str:
        """A path relative to the config dir; absolute filesystem paths never leave this module."""
        try:
            return str(path.relative_to(self._root))
        except ValueError:
            return path.name

    def _load_file(self, kind: str, path: Path) -> tuple[BaseModel | None, str | None]:
        """Return (object, etag) or (None, error message). Never raises."""
        obj_id = path.stem
        try:
            self._check_id(kind, obj_id)
        except ConfigInvalid as exc:
            return None, _short(exc)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            return None, f"unreadable: {_short(exc)}"
        try:
            data = yaml.safe_load(raw.decode("utf-8"))
        except (yaml.YAMLError, UnicodeDecodeError) as exc:
            return None, f"invalid yaml: {_short(exc)}"
        if not isinstance(data, dict):
            return None, "invalid yaml: top level must be a mapping"
        try:
            obj = MODEL_BY_KIND[kind].model_validate(data)
        except ValidationError as exc:
            return None, _describe(exc, "invalid config")
        if obj.id != obj_id:
            return None, f"invalid config: filename {obj_id!r} does not match id {obj.id!r}"
        if kind == "request" and path.parent.name != obj.provider:
            return None, (
                f"invalid config: request {obj.id!r} is not under its provider "
                f"directory {obj.provider!r}"
            )
        return obj, hashlib.sha256(raw).hexdigest()

    def reload(self) -> None:
        """Re-read every config file. Reads and validates; executes nothing."""
        with self._lock:
            objects: dict[str, dict[str, BaseModel]] = {k: {} for k in KINDS}
            etags: dict[str, dict[str, str]] = {k: {} for k in KINDS}
            errors: list[dict[str, str]] = []
            for kind in KINDS:
                for path in self._files(kind):
                    obj, info = self._load_file(kind, path)
                    if obj is None:
                        # The file changed on disk, so its etag changed: a stale PUT must get 409.
                        bad_etag = self._file_etag(path)
                        errors.append({"path": self._rel(path), "kind": kind, "id": path.stem,
                                       "etag": bad_etag or "", "message": info or "invalid config"})
                        if bad_etag is not None:
                            etags[kind][path.stem] = bad_etag
                        # An invalid file keeps the last valid object active.
                        previous = self._objects[kind].get(path.stem)
                        if previous is not None:
                            objects[kind][path.stem] = previous
                        continue
                    objects[kind][obj.id] = obj
                    etags[kind][obj.id] = info or ""
            self._objects = objects
            self._etags = etags
            self._errors = errors
            changed = self._refresh_versions()
        self._notify(changed)

    # -------------------------------------------------------------- reading

    def snapshot(self) -> dict[str, dict[str, BaseModel]]:
        """A value copy of everything currently loaded, per kind and id."""
        with self._lock:
            out: dict[str, dict[str, BaseModel]] = {}
            for kind in KINDS:
                out[kind] = {oid: self._copy(obj) for oid, obj in self._objects[kind].items()}
            return out

    @staticmethod
    def _copy(obj: BaseModel) -> BaseModel:
        try:
            return obj.model_copy(deep=True)
        except Exception:  # pragma: no cover - exotic body payloads
            return obj

    def iter_all(self) -> Iterator[tuple[str, BaseModel]]:
        with self._lock:
            items = [(kind, oid, obj) for kind in KINDS for oid, obj in self._objects[kind].items()]
        for kind, _oid, obj in sorted(items, key=lambda t: (t[0], t[1])):
            yield kind, self._copy(obj)

    def get(self, kind: str, obj_id: str) -> BaseModel | None:
        self._check_kind(kind)
        with self._lock:
            obj = self._objects[kind].get(obj_id)
            return self._copy(obj) if obj is not None else None

    def etag(self, kind: str, obj_id: str) -> str | None:
        self._check_kind(kind)
        with self._lock:
            return self._etags[kind].get(obj_id)

    def errors(self) -> list[dict[str, str]]:
        with self._lock:
            return [dict(err) for err in self._errors]

    # -------------------------------------------------------------- writing

    def save(self, kind: str, obj: BaseModel, *, etag: str | None = None) -> str:
        """Validate, atomically write, and return the new etag."""
        self._check_kind(kind)
        if not isinstance(obj, BaseModel):
            raise ConfigInvalid(f"{kind} object must be a {MODEL_BY_KIND[kind].__name__}")
        # Id first: nothing is ever built from an unvalidated id.
        obj_id = self._check_id(kind, getattr(obj, "id", None))
        data = obj.model_dump()
        try:
            obj = MODEL_BY_KIND[kind].model_validate(data)
        except ValidationError as exc:
            raise ConfigInvalid(_describe(exc, f"invalid {kind}")) from None
        if obj.id != obj_id:
            raise ConfigInvalid(f"{kind} id {obj_id!r} does not match id {obj.id!r}")

        with self._lock:
            self._check_references(kind, obj)
            current = self._etags[kind].get(obj_id)
            if etag is not None:
                if etag == "":
                    if current is not None:
                        raise EtagMismatch(f"{kind} {obj_id} already exists")
                elif current is None or current != etag:
                    raise EtagMismatch(f"{kind} {obj_id} etag is stale")

            path = self._path_for(kind, obj.id)
            try:
                payload = yaml.safe_dump(
                    obj.model_dump(mode="json"),
                    sort_keys=True,
                    allow_unicode=True,
                    default_flow_style=False,
                ).encode("utf-8")
            except (yaml.YAMLError, TypeError, ValueError) as exc:
                raise ConfigInvalid(f"cannot serialise {kind} {obj_id}: {_short(exc)}") from None
            new_etag = self._atomic_write(path, payload)
            self._objects[kind][obj.id] = obj
            self._etags[kind][obj.id] = new_etag
            self._errors = [e for e in self._errors if not (e.get("kind") == kind and e.get("id") == obj.id)]
            changed = self._refresh_versions()
        self._notify(changed)
        return new_etag

    def delete(self, kind: str, obj_id: str, *, etag: str | None = None) -> None:
        """Remove one object. ``etag`` (if given) must be current. A file that is invalid on disk and
        has no valid version can only be removed with the etag listed in ``errors()``."""
        self._check_kind(kind)
        self._check_id(kind, obj_id)
        with self._lock:
            current = self._etags[kind].get(obj_id)
            if obj_id in self._objects[kind]:
                if etag is not None and etag != current:
                    raise EtagMismatch(f"{kind} {obj_id} etag is stale")
                self._check_not_referenced(kind, obj_id)
            elif any(e.get("kind") == kind and e.get("id") == obj_id for e in self._errors):
                if not etag or etag != current:
                    raise EtagMismatch(f"{kind} {obj_id} is invalid on disk; delete needs its current etag")
            else:
                raise ConfigInvalid(f"no {kind} {obj_id}")
            self._unlink(self._path_for(kind, obj_id))
            self._objects[kind].pop(obj_id, None)
            self._etags[kind].pop(obj_id, None)
            self._errors = [e for e in self._errors if not (e.get("kind") == kind and e.get("id") == obj_id)]
            changed = self._refresh_versions()
        self._notify(changed)

    # ------------------------------------------------------------ references

    def _check_references(self, kind: str, obj: BaseModel) -> None:
        """Every reference must already exist in the loaded, valid config."""
        if kind == "request":
            missing = [obj.id] if obj.provider not in self._objects["provider"] else []
            if missing:
                raise ConfigInvalid(f"request {obj.id}: unknown provider {obj.provider!r}")
            for action in self._objects["action"].values():
                if action.request == obj.id:
                    self._check_action_policy(action, obj)
        elif kind == "card":
            unknown = [r for r in obj.request_ids() if r not in self._objects["request"]]
            if unknown:
                raise ConfigInvalid(f"card {obj.id}: unknown request(s) {', '.join(unknown)}")
        elif kind == "board":
            unknown = [i.card for i in obj.items if i.card not in self._objects["card"]]
            if unknown:
                raise ConfigInvalid(f"board {obj.id}: unknown card(s) {', '.join(unknown)}")
        elif kind == "action":
            request = self._objects["request"].get(obj.request)
            if request is None:
                raise ConfigInvalid(f"action {obj.id}: unknown request {obj.request!r}")
            self._check_action_policy(obj, request)

    @staticmethod
    def _check_action_policy(action: Any, request: Any) -> None:
        """access must match the request's effect; approval: never on a write needs the owner's waiver."""
        write = request.resolved_effect() == "write"
        if write and action.access == "read":
            raise ConfigInvalid(f"action {action.id}: access is read but request {request.id} writes")
        if write and action.approval == "never" and not action.owner_waives_approval:
            raise ConfigInvalid(f"action {action.id}: approval never on a write needs owner_waives_approval: true")

    def _check_not_referenced(self, kind: str, obj_id: str) -> None:
        if kind == "provider":
            users = [r.id for r in self._objects["request"].values() if r.provider == obj_id]
        elif kind == "request":
            users = [c.id for c in self._objects["card"].values() if obj_id in c.request_ids()]
            users += [a.id for a in self._objects["action"].values() if a.request == obj_id]
        elif kind == "card":
            users = [b.id for b in self._objects["board"].values() if any(i.card == obj_id for i in b.items)]
        else:
            users = []
        if users:
            raise ConfigInvalid(f"cannot delete {kind} {obj_id}: still referenced by {', '.join(sorted(users))}")

    # ------------------------------------------------------- action versions

    def _version_of(self, action_id: str) -> str | None:
        action = self._objects["action"].get(action_id)
        if action is None:
            return None
        request = self._objects["request"].get(action.request)
        if request is None:
            return None
        provider = self._objects["provider"].get(request.provider)
        if provider is None:
            return None
        return models.action_version(action, request, provider)

    def _refresh_versions(self) -> set[str]:
        """Recompute action versions; return the ids whose version changed."""
        current = {action_id: self._version_of(action_id) for action_id in self._objects["action"]}
        changed = {aid for aid, version in current.items() if self._versions.get(aid) != version}
        changed |= {aid for aid, version in self._versions.items() if aid not in current and version is not None}
        self._versions = current
        return changed

    def action_version(self, action_id: str) -> str | None:
        """Computed version of one action; never stored in a file."""
        with self._lock:
            return self._version_of(action_id)

    def on_change(self, callback: Callable[[list[str]], None]) -> Callable[[], None]:
        """Register a listener called with the action ids whose version changed."""
        with self._lock:
            self._listeners.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)

        return unsubscribe

    def _notify(self, changed: set[str]) -> None:
        if not changed:
            return
        with self._lock:
            listeners = list(self._listeners)
        ids = sorted(changed)
        for callback in listeners:
            try:
                callback(ids)
            except Exception:  # a listener must never break the store
                logger.exception("worlds config change listener failed")

    # ------------------------------------------------------------ disk i/o

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except BaseException:
            if tmp.exists():
                tmp.unlink()
            raise
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
