"""Encrypted worlds backup/restore — the SOS escape hatch.

One command produces ONE encrypted file containing the full-restore
boundary (docs/repo/WIRING-READINESS.md §"Proposed full-restore
boundary"): world, journal, per-user trees, identities, reminders,
apps, proposals, local connection overrides, OIDC *config only*,
discovery, reconciler/lab desired state, theme packs, and template
sources. A fresh build can import that file and be the same instance.

Owner fears this module is built to honor:

- **Private data never leaks.** The archive is encrypted before it
  touches disk (scrypt KDF → AES-256-GCM, header bound as AAD). The
  plaintext header carries only structure — member names, KDF params,
  manifest hash — never content.
- **Passphrases are never stored or logged.** They are accepted at
  call time only, used to derive a key in memory, and dropped. No
  key material, passphrase, or secret value is ever written to the
  archive, a log, or a Result payload.
- **Fail closed.** Without the ``crypto`` extra (``cryptography``),
  both backup and restore return ``unavailable`` and write nothing —
  there is no plaintext fallback, because an unencrypted "backup" of
  private data is the exact leak this exists to prevent. Wrong
  passphrase or a tampered archive fails authentication BEFORE any
  byte is written to the live data tree.

Never included (ephemeral/regenerable, per the restore boundary):
``sessions.json``, ``memory.fts5.db*``.
``vault.enc`` (instance and per-user) is included ONLY with the
explicit ``include_vault=True`` — it is already encrypted at rest, and
decision #4 in docs/history/PRODUCT-VISION-HANDOFF.md allows it in a
full-restore artifact encrypted-only, never by default.

OIDC caveat: ``oidc.json`` is archived as CONFIG ONLY. By design it
holds ``client_secret_env`` (the env var *name*); as defense in depth
this module additionally strips any inline secret-shaped key/value it
finds in that file before archiving, and says so in the report.

Ordinary exports (``export.settings_export`` / ``export.world_export``)
remain secret-free by design; this module is the disaster-
recovery path, not a sharing path.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from .envelope import Result, fail, ok

# Real encryption uses `cryptography`. Like vault.py, the dependency is
# optional for minimal installs but the module FAILS CLOSED without it:
# backup/restore return `unavailable` and write nothing. There is no
# plaintext or base64 fallback — those are not encryption.
try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover - exercised via monkeypatch in tests
    _HAS_CRYPTO = False

FORMAT_ID = "pw-worlds-backup/1"
ARCHIVE_SUFFIX = ".pwbackup"

# scrypt parameters (memory-hard; OWASP acceptable as of 2024).
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 32
NONCE_LENGTH = 12  # AES-GCM standard 96-bit nonce

_CRYPTO_MISSING_MSG = (
    "cryptography package not installed; worlds backup/restore is "
    "unavailable without real encryption (no plaintext fallback "
    "exists by design). Install with: pip install 'personal-world[crypto]'"
)

# ── restore boundary ─────────────────────────────────────────────────
# Files under the instance data dir that are part of the boundary.
DATA_BOUNDARY_FILES = (
    "world.json",
    "journal.ndjson",
    "users.json",
    "reminders.json",
    "apps.json",
    "proposals.json",
    "chat-history.ndjson",
)
# Whole subtrees under the data dir that are user-owned state.
DATA_BOUNDARY_TREES = ("users", "theme-packs", "template-sources")
# Files under the app config dir (private runtime config).
CONFIG_BOUNDARY_FILES = ("connections.local.json", "oidc.json")
# Files/dirs under the per-user config home (~/.config/personal-world).
HOME_BOUNDARY_FILES = ("lab.json",)
HOME_BOUNDARY_TREES = ("reconciler/desired", "lab/desired")

# Ephemeral / regenerable — NEVER archived, never restored, even if an
# archive from some other tool somehow contains them.
NEVER_NAMES = frozenset({"sessions.json"})
NEVER_PREFIXES = ("memory.fts5.db",)

# Operational instance files that are always present and intentionally
# outside the boundary: credentials and the first-run marker. The module
# docstring accounts for them, so they need no per-backup report line —
# unlike UNRECOGNIZED entries, which must never stay silent.
OPERATIONAL_NAMES = frozenset({".env", "setup-complete"})

# Keys whose VALUES must never enter an archive even if an operator
# hand-edited them into a config-only file. *_env / *_ref indirection
# keys are the allowed shape and pass through.
SECRET_KEY_HINTS = (
    "client_secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "password",
    "passwd",
)


def default_home_config_dir() -> Path:
    """Per-user config home where discovery/reconciler/lab state lives."""
    return Path("~/.config/personal-world").expanduser()


def _is_never(name: str) -> bool:
    return name in NEVER_NAMES or name.startswith(NEVER_PREFIXES)


def _unrecognized_data_entries(data_dir: Path) -> list[str]:
    """Top-level data-dir entries the boundary never mentions.

    These are REPORTED, not silently dropped: a future local store under
    ``data/`` must show up in every backup report as NOT archived.
    Vanishing from an "SOS backup" without a word is how a backup turns
    into a false claim (lane B restore drill finding, 2026-09-22). Operational
    and never-archived names are exempt — the module docstring already
    accounts for them, and re-listing them every run is noise, not
    accuracy.
    """
    covered = set(DATA_BOUNDARY_FILES) | set(DATA_BOUNDARY_TREES) | {"vault.enc"}
    notes: list[str] = []
    try:
        top = sorted(data_dir.iterdir())
    except OSError:
        return notes
    for path in top:
        name = path.name
        if name in covered or name in OPERATIONAL_NAMES or _is_never(name):
            continue
        notes.append(
            f"data/{name} (NOT recognized by the backup boundary — not "
            "archived; if this is user state, add it to DATA_BOUNDARY_* "
            "and extend the restore tests)"
        )
    return notes


def _is_secret_key(key: str) -> bool:
    low = key.lower()
    if low.endswith(("_env", "_ref")):
        return False
    return (
        any(hint in low for hint in SECRET_KEY_HINTS)
        or low == "secret"
        or low == "token"
    )


def _sanitize_config_json(raw: bytes, arcname: str) -> tuple[bytes | None, str | None]:
    """Strip inline secret values from a config-only archive member.

    Returns (sanitized_bytes, warning). Unparseable content is excluded
    rather than archived blind — fail closed.
    """
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, f"{arcname} excluded: not valid JSON ({e.__class__.__name__})"

    stripped: list[str] = []

    def walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if _is_secret_key(str(k)):
                    stripped.append(k)
                    out[k] = "<stripped-by-worlds-backup>"
                else:
                    out[k] = walk(v)
            return out
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        return obj

    clean = walk(data)
    warning = None
    if stripped:
        warning = (
            f"{arcname}: inline secret values stripped before archiving "
            f"(keys: {', '.join(sorted(set(stripped)))}); keep secrets in "
            "env indirection (*_env) or the vault"
        )
    return json.dumps(clean, indent=2).encode("utf-8"), warning


def _collect_members(
    data_dir: Path,
    config_dir: Path | None,
    home_config_dir: Path | None,
    include_vault: bool,
) -> tuple[list[tuple[str, bytes | Path]], list[str]]:
    """Walk the restore boundary; return (members, excluded_notes).

    A member is (arcname, source) where source is a Path to copy or
    bytes to embed (sanitized config). Arcnames are namespaced:
    ``data/…`` (instance data dir), ``config/…`` (app config dir),
    ``home/…`` (per-user config home). Missing files are simply not
    members — an absent optional file is a normal state, not an error.
    """
    members: list[tuple[str, bytes | Path]] = []
    excluded: list[str] = [
        "sessions.json (ephemeral; never archived)",
        "memory.fts5.db (regenerable from journal; never archived)",
    ]
    if not include_vault:
        excluded.append(
            "vault.enc (excluded by default; already encrypted at rest — "
            "re-run with --include-vault for secret portability)"
        )

    def want_file(path: Path, arcname: str) -> None:
        name = path.name
        if _is_never(name):
            return
        if name == "vault.enc" and not include_vault:
            return
        if path.is_file():
            members.append((arcname, path))

    def want_tree(root: Path, prefix: str) -> None:
        if not root.is_dir():
            return
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            name = path.name
            if _is_never(name):
                continue
            if name == "vault.enc" and not include_vault:
                excluded.append(f"{prefix}/{rel} (vault; excluded by default)")
                continue
            members.append((f"{prefix}/{rel}", path))

    # Instance data dir.
    for fname in DATA_BOUNDARY_FILES:
        want_file(data_dir / fname, f"data/{fname}")
    want_file(data_dir / "vault.enc", "data/vault.enc")
    for tree in DATA_BOUNDARY_TREES:
        want_tree(data_dir / tree, f"data/{tree}")

    # App config dir (private runtime config).
    if config_dir is not None:
        for fname in CONFIG_BOUNDARY_FILES:
            path = config_dir / fname
            if not path.is_file():
                continue
            arcname = f"config/{fname}"
            if fname == "oidc.json":
                sanitized, warning = _sanitize_config_json(path.read_bytes(), arcname)
                if sanitized is None:
                    excluded.append(warning or f"{arcname} excluded")
                    continue
                if warning:
                    excluded.append(warning)
                members.append((arcname, sanitized))
            else:
                members.append((arcname, path))

    # Per-user config home (discovery / reconciler / lab desired state).
    if home_config_dir is not None:
        for fname in HOME_BOUNDARY_FILES:
            want_file(home_config_dir / fname, f"home/{fname}")
        for tree in HOME_BOUNDARY_TREES:
            want_tree(home_config_dir / tree, f"home/{tree}")

    return members, excluded + _unrecognized_data_entries(data_dir)


def _build_tar(members: list[tuple[str, bytes | Path]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for arcname, source in members:
            info = tarfile.TarInfo(name=arcname)
            if isinstance(source, Path):
                stat = source.stat()
                info.size = stat.st_size
                info.mtime = int(stat.st_mtime)
                info.mode = 0o600
                with source.open("rb") as fh:
                    tar.addfile(info, fh)
            else:
                info.size = len(source)
                info.mtime = int(time.time())
                info.mode = 0o600
                tar.addfile(info, io.BytesIO(source))
    return buf.getvalue()


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=KEY_LENGTH, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(passphrase.encode("utf-8"))


def _encrypt(
    tar_bytes: bytes, passphrase: str, included: list[str], excluded: list[str]
) -> bytes:
    """Produce the archive: plaintext structural header, newline, then
    AES-256-GCM ciphertext. The exact header bytes are bound as AAD, so
    tampering with the header fails authentication too."""
    salt = os.urandom(16)
    nonce = os.urandom(NONCE_LENGTH)
    key = _derive_key(passphrase, salt)
    header = {
        "format": FORMAT_ID,
        "version": 1,
        "created_at": time.time(),
        "kdf": {
            "name": "scrypt",
            "n": SCRYPT_N,
            "r": SCRYPT_R,
            "p": SCRYPT_P,
            "salt": salt.hex(),
            "key_length": KEY_LENGTH,
        },
        "cipher": "AES-256-GCM",
        "nonce": nonce.hex(),
        "manifest_sha256": hashlib.sha256(tar_bytes).hexdigest(),
        "included": included,
        "excluded": excluded,
    }
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
    # The canonical header bytes are bound as AAD: any edit to the
    # plaintext header (swap a member list, change KDF params) fails
    # GCM authentication on restore.
    ciphertext = AESGCM(key).encrypt(nonce, tar_bytes, associated_data=header_bytes)
    return header_bytes + b"\n" + ciphertext


def _split_archive(blob: bytes) -> tuple[dict[str, Any], bytes]:
    head, _, rest = blob.partition(b"\n")
    if not rest:
        raise ValueError("archive is truncated (no ciphertext after header)")
    try:
        header = json.loads(head.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"archive header is not valid JSON: {e}") from e
    if not isinstance(header, dict):
        raise ValueError("archive header is not an object")
    return header, rest


def _decrypt(archive_path: Path, passphrase: str) -> tuple[dict[str, Any], bytes]:
    """Verify header + auth tag + manifest hash. Returns (header,
    tar_bytes) only when everything authenticates; raises ValueError
    (corrupt/tampered) or PermissionError (wrong passphrase) otherwise.
    Nothing is written to disk by this function."""
    blob = archive_path.read_bytes()
    header, ciphertext = _split_archive(blob)
    if header.get("format") != FORMAT_ID:
        raise ValueError(
            f"not a worlds backup archive (format={header.get('format')!r})"
        )
    kdf = header.get("kdf") or {}
    if kdf.get("name") != "scrypt" or header.get("cipher") != "AES-256-GCM":
        raise ValueError("unsupported kdf/cipher in archive header")
    try:
        salt = bytes.fromhex(kdf["salt"])
        nonce = bytes.fromhex(header["nonce"])
    except (KeyError, ValueError) as e:
        raise ValueError(f"malformed archive header: {e}") from e

    head_bytes = blob.split(b"\n", 1)[0]
    key = _derive_key(passphrase, salt)
    try:
        tar_bytes = AESGCM(key).decrypt(nonce, ciphertext, associated_data=head_bytes)
    except InvalidTag as e:
        raise PermissionError(
            "decryption failed authentication: wrong passphrase or the "
            "archive was tampered with"
        ) from e
    digest = hashlib.sha256(tar_bytes).hexdigest()
    if digest != header.get("manifest_sha256"):
        raise ValueError("manifest hash mismatch: archive content is corrupt")
    return header, tar_bytes


def _safe_relpath(arcname: str) -> str | None:
    """Normalized relative path for a tar member, or None if unsafe."""
    if not arcname or arcname.startswith(("/", "\\")) or ":" in arcname.split("/")[0]:
        return None
    parts: list[str] = []
    for part in arcname.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            return None
        parts.append(part)
    return "/".join(parts) if parts else None


# ── public API ────────────────────────────────────────────────────────


def backup(
    data_dir: Path | str,
    target_path: Path | str,
    passphrase: str,
    include_vault: bool = False,
    *,
    config_dir: Path | str | None = None,
    home_config_dir: Path | str | None = None,
) -> Result:
    """Create ONE encrypted archive of the full-restore boundary.

    The passphrase is used at call time only — never stored, never
    logged, never placed in the returned Result. Fails closed without
    the cryptography extra: returns `unavailable` and writes nothing.
    """
    if not _HAS_CRYPTO:
        return fail("unavailable", warnings=[_CRYPTO_MISSING_MSG])
    if not passphrase:
        return fail("rejected", warnings=["empty passphrase refused"])

    data_dir = Path(data_dir)
    target_path = Path(target_path)
    if not data_dir.is_dir():
        return fail("not_found", warnings=[f"data dir does not exist: {data_dir}"])

    members, excluded = _collect_members(
        data_dir,
        Path(config_dir) if config_dir is not None else None,
        Path(home_config_dir) if home_config_dir is not None else None,
        include_vault,
    )
    if not members:
        return fail(
            "empty",
            warnings=[
                "nothing to back up: no restore-boundary files found "
                f"under {data_dir} (is this the right --data-dir?)"
            ],
            data={"included": [], "excluded": excluded},
        )

    tar_bytes = _build_tar(members)
    included = [arcname for arcname, _ in members]
    blob = _encrypt(tar_bytes, passphrase, included, excluded)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=str(target_path.parent), prefix=".pwbackup-", suffix=".part"
    )
    try:
        with os.fdopen(tmp_fd, "wb") as fh:
            fh.write(blob)
        os.replace(tmp_name, target_path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise

    return ok(
        "written",
        changed=True,
        data={
            "path": str(target_path),
            "bytes": len(blob),
            "format": FORMAT_ID,
            "vault_included": include_vault,
            "included": included,
            "excluded": excluded,
        },
        warnings=[w for w in excluded if "stripped" in w],
        actions=[
            "copy the archive OFF this machine and remember the passphrase "
            "— neither is recoverable from the other",
        ],
    )


def restore(
    data_dir: Path | str,
    archive_path: Path | str,
    passphrase: str,
    overwrite: bool = False,
    *,
    config_dir: Path | str | None = None,
    home_config_dir: Path | str | None = None,
) -> Result:
    """Import an encrypted archive into a (typically fresh) instance.

    Verifies header, auth tag, and manifest hash BEFORE writing
    anything. Decrypts to a temp dir, then copies create-if-absent
    (default) or replaces (``overwrite=True``). Ephemeral members
    (sessions/fts5) are refused even if present. Returns a per-file report: restored / skipped / refused. Fails closed on
    wrong passphrase, tampering, or missing cryptography.
    """
    if not _HAS_CRYPTO:
        return fail("unavailable", warnings=[_CRYPTO_MISSING_MSG])
    if not passphrase:
        return fail("rejected", warnings=["empty passphrase refused"])

    archive_path = Path(archive_path)
    if not archive_path.is_file():
        return fail("not_found", warnings=[f"no archive at {archive_path}"])

    try:
        header, tar_bytes = _decrypt(archive_path, passphrase)
    except PermissionError as e:
        return fail("unauthorized", warnings=[str(e)])
    except ValueError as e:
        return fail("corrupt", warnings=[str(e)])

    roots = {
        "data": Path(data_dir),
        "config": Path(config_dir) if config_dir is not None else None,
        "home": (
            Path(home_config_dir)
            if home_config_dir is not None
            else default_home_config_dir()
        ),
    }

    restored: list[str] = []
    skipped: list[str] = []
    refused: list[str] = []

    with tempfile.TemporaryDirectory(prefix="pw-restore-") as tmp:
        tmp_dir = Path(tmp)
        try:
            with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tar:
                safe_members = []
                for m in tar.getmembers():
                    if not m.isfile():
                        refused.append(f"{m.name} (not a regular file)")
                        continue
                    rel = _safe_relpath(m.name)
                    if rel is None:
                        refused.append(f"{m.name} (unsafe path; refused)")
                        continue
                    m.name = rel
                    safe_members.append(m)
                tar.extractall(tmp_dir, members=safe_members, filter="data")
        except (tarfile.TarError, EOFError) as e:
            return fail(
                "corrupt", warnings=[f"archive payload is not a valid tar: {e}"]
            )

        for rel_path in sorted(tmp_dir.rglob("*")):
            if not rel_path.is_file():
                continue
            arcname = rel_path.relative_to(tmp_dir).as_posix()
            root_name, _, sub = arcname.partition("/")
            target_root = roots.get(root_name)
            if not sub or target_root is None:
                refused.append(f"{arcname} (unknown archive root; refused)")
                continue
            if _is_never(Path(sub).name):
                refused.append(f"{arcname} (ephemeral/regenerable; never restored)")
                continue
            dest = target_root / sub
            # Defense in depth: the resolved destination must stay inside
            # its root even if a member name was exotic.
            if not dest.resolve().is_relative_to(target_root.resolve()):
                refused.append(f"{arcname} (escapes restore root; refused)")
                continue
            if dest.exists() and not overwrite:
                skipped.append(f"{arcname} (exists; pass --overwrite to replace)")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(rel_path, dest)
            os.chmod(dest, 0o600)
            restored.append(arcname)

    if not restored and not skipped:
        return fail(
            "refused",
            warnings=[f"no file could be restored ({len(refused)} refused)"],
            data={
                "restored": restored,
                "skipped": skipped,
                "refused": refused,
                "header": {
                    k: header[k]
                    for k in ("format", "created_at", "manifest_sha256")
                    if k in header
                },
            },
        )
    return ok(
        "restored",
        changed=bool(restored),
        data={
            "restored": restored,
            "skipped": skipped,
            "refused": refused,
            "archive_format": header.get("format"),
            "archive_created_at": header.get("created_at"),
        },
        warnings=[f"{len(refused)} member(s) refused"] if refused else [],
        actions=(
            ["restart the app so registries reload restored state"] if restored else []
        ),
    )


# ── API registration (NOT wired yet — api.py is contested) ───────────
#
# Intended routes, all STEP-UP GATED (a fresh session must re-prove
# identity before backup/restore; these endpoints hand over the whole
# world or replace it):
#
#   POST /api/worlds/backup          {passphrase, include_vault}
#                                    → {download, included, excluded}
#   GET  /api/worlds/backup/download/{token}   one-time archive download
#   POST /api/worlds/restore         {passphrase, archive_b64, overwrite}
#                                    → {restored, skipped, refused}
#
# The passphrase travels in the request BODY only (never a query
# string, never a header that proxies log) and is typed as
# pydantic SecretStr so it is redacted from reprs and any accidental
# log line. Download tokens are single-use: the encrypted archive is
# deleted from server temp storage the moment it is served, and stale
# tokens expire.
#
# The orchestrator wires this later with:
#
#   from personal_world.worlds_backup import register_worlds_backup
#   register_worlds_backup(app, data_dir=DATA_DIR, config_dir=CONFIG_DIR,
#                          step_up=<the real step-up dependency>)

_PENDING_DOWNLOADS: dict[str, tuple[Path, float]] = {}
_DOWNLOAD_TTL_SECONDS = 300.0


# Request models are at module level on purpose: with
# `from __future__ import annotations`, FastAPI resolves route
# annotations against the *module* globals — models defined inside the
# registration closure would be invisible to it. The SAME rule applies
# to response classes: `-> FileResponse` on the download route could not
# be resolved while FileResponse lived only inside register_worlds_backup
# (discovered by actually building app.openapi() — S2 contract fix #1).
from fastapi.responses import FileResponse  # noqa: E402  (fastapi is a core dep)
from pydantic import BaseModel, SecretStr  # noqa: E402  (pydantic is a core dep)


class WorldsBackupRequest(BaseModel):
    """Passphrase as SecretStr: redacted from reprs and any accidental
    log line. Travels in the request body only — never a query string."""

    passphrase: SecretStr
    include_vault: bool = False


class WorldsRestoreRequest(BaseModel):
    passphrase: SecretStr
    archive_b64: str
    overwrite: bool = False


def register_worlds_backup(
    app: Any,
    *,
    data_dir: Path | str,
    config_dir: Path | str | None = None,
    home_config_dir: Path | str | None = None,
    step_up: Any = None,
    owner_gate: Any = None,
) -> None:
    """Register the step-up-gated worlds backup/restore routes on a
    FastAPI app. ``step_up`` MUST be the app's real step-up auth
    dependency; registration refuses without it (fail closed — an
    ungated whole-world export endpoint must never exist by accident).
    ``owner_gate`` MUST be a dependency that refuses every caller who is
    not an owner or admin; registration refuses without it too. Both run
    before the handler, so a refused caller never creates or consumes a
    one-time download token.
    """
    if step_up is None:
        raise ValueError(
            "register_worlds_backup requires the step-up dependency; "
            "refusing to register ungated backup/restore routes"
        )

    if owner_gate is None:
        raise ValueError(
            "register_worlds_backup requires the owner dependency; "
            "refusing to register routes any signed-in person could use"
        )

    from fastapi import Depends, HTTPException
    from fastapi.responses import FileResponse

    data_dir = Path(data_dir)
    config_dir = Path(config_dir) if config_dir is not None else None
    home = (
        Path(home_config_dir)
        if home_config_dir is not None
        else default_home_config_dir()
    )
    gate = [Depends(step_up), Depends(owner_gate)]

    def _sweep() -> None:
        now = time.time()
        for token in [
            t
            for t, (_, created) in _PENDING_DOWNLOADS.items()
            if now - created > _DOWNLOAD_TTL_SECONDS
        ]:
            path, _ = _PENDING_DOWNLOADS.pop(token)
            path.unlink(missing_ok=True)

    @app.post("/api/worlds/backup", dependencies=gate)
    def worlds_backup(body: WorldsBackupRequest) -> dict[str, Any]:
        _sweep()
        import base64 as _b64

        fd, tmp_path = tempfile.mkstemp(prefix="pw-worlds-", suffix=ARCHIVE_SUFFIX)
        os.close(fd)
        result = backup(
            data_dir,
            Path(tmp_path),
            body.passphrase.get_secret_value(),
            include_vault=body.include_vault,
            config_dir=config_dir,
            home_config_dir=home,
        )
        if not result.ok:
            Path(tmp_path).unlink(missing_ok=True)
            code = 503 if result.status == "unavailable" else 400
            raise HTTPException(
                status_code=code, detail=result.warnings or result.status
            )
        token = _b64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")
        _PENDING_DOWNLOADS[token] = (Path(tmp_path), time.time())
        return {
            "download": f"/api/worlds/backup/download/{token}",
            "one_time": True,
            "expires_in_seconds": _DOWNLOAD_TTL_SECONDS,
            "included": (result.data or {}).get("included", []),
            "excluded": (result.data or {}).get("excluded", []),
            "vault_included": bool(body.include_vault),
        }

    @app.get("/api/worlds/backup/download/{token}", dependencies=gate)
    def worlds_backup_download(token: str) -> FileResponse:
        entry = _PENDING_DOWNLOADS.pop(token, None)
        if entry is None:
            # LANG-050 presentation mapping: the human message leads; the
            # operator code stays in the same body as machine-facing data.
            raise HTTPException(
                status_code=404,
                detail={
                    "message": (
                        "This one-time download link is no longer "
                        "available. Create a new backup to get another link."
                    ),
                    "error_code": "download_token_unknown_or_expired",
                },
            )
        path, _ = entry
        from starlette.background import BackgroundTask

        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=f"personal-worlds-backup{ARCHIVE_SUFFIX}",
            # One-time: the encrypted temp file is deleted once served.
            background=BackgroundTask(path.unlink, missing_ok=True),
        )

    @app.post("/api/worlds/restore", dependencies=gate)
    def worlds_restore(body: WorldsRestoreRequest) -> dict[str, Any]:
        import base64 as _b64

        try:
            blob = _b64.b64decode(body.archive_b64, validate=True)
        except Exception as _err:
            raise HTTPException(
                status_code=400, detail="archive_b64 is not valid base64"
            ) from _err
        fd, tmp_path = tempfile.mkstemp(prefix="pw-restore-", suffix=ARCHIVE_SUFFIX)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(blob)
            result = restore(
                data_dir,
                Path(tmp_path),
                body.passphrase.get_secret_value(),
                overwrite=body.overwrite,
                config_dir=config_dir,
                home_config_dir=home,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        if not result.ok:
            code = {"unavailable": 503, "unauthorized": 403, "not_found": 404}.get(
                result.status, 400
            )
            raise HTTPException(
                status_code=code, detail=result.warnings or result.status
            )
        return result.data or {}
