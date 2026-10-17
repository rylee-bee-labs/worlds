"""CLI. Every command prints the stable JSON envelope with --json;
human output otherwise.

Only two surfaces remain after the front-door rebuild (ADR-0008, Phase 4):

* the framework gate — ``framework validate`` and ``framework validate-packs``;
* Memory's backup pair — ``memory backup`` mirrors ``POST /api/memory/backup``
  and ``memory restore`` wraps ``worlds.memory_store.restore_backup``.

The retired ADR-0001 verbs (status, daily, journal, prefs, updates, recipes,
worlds, …) and their modules are gone; the gate's JSON envelope and exit codes
are unchanged (docs/rebuild/FRAMEWORK-GATE.md)."""

import argparse
import json
import sys
from pathlib import Path

from .envelope import EXIT_ERROR, EXIT_OK, Result
from .framework import (
    validate_framework,
    validate_participant_packs,
)


def _emit(result: Result, as_json: bool, exit_code: int | None = None) -> int:
    if as_json:
        print(result.model_dump_json(indent=2))
    else:
        head = f"{result.status}: {'ok' if result.ok else 'not ok'}"
        print(head)
        for w in result.warnings:
            print(f"  ! {w}")
        for a in result.actions:
            print(f"  * {a}")
        if result.data is not None:
            print(json.dumps(result.data, indent=2, default=str))
    if exit_code is not None:
        return exit_code
    return EXIT_OK if result.ok else EXIT_ERROR


def cmd_framework_validate(args) -> int:
    """Validate the front-door framework invariants (ADR-0008 decision 3).

    Checks the C1 config store (schema, ids, references, no inline secrets),
    the shipped recipes, the core compose's provider independence, the
    zero-provider/zero-model baseline boot, and the shareable Memory exports.
    Read-only with respect to the configured config directory."""
    result = validate_framework(Path(args.config_dir))
    payload = {
        "violations": [
            {"rule": violation.rule, "detail": violation.detail}
            for violation in result.violations
        ],
        "count": len(result.violations),
    }
    if result.ok:
        return _emit(Result(ok=True, status="healthy", data=payload), args.json)
    return _emit(
        Result(
            ok=False,
            status="unhealthy",
            warnings=[f"[{v.rule}] {v.detail}" for v in result.violations],
            data=payload,
        ),
        args.json,
        EXIT_ERROR,
    )


def cmd_framework_validate_packs(args) -> int:
    """Validate every participant pack under .project/participants/.

    Pure deterministic check: parse every *.yaml, fail closed on
    malformed YAML, missing required keys, schema-namespace violations,
    and duplicate pack ids. Does NOT attest contracts; that is the
    role of the upstream play-nice-contracts library. Project-neutral
    so any agent harness, CI run, or human can drive it."""
    project_root = Path(__file__).resolve().parents[2]
    packs_dir = project_root / ".project" / "participants"
    result = validate_participant_packs(packs_dir, project_root=project_root)
    payload = {
        "packs_dir": str(packs_dir),
        "violations": [str(v) for v in result.violations],
        "count": len(result.violations),
    }
    if result.ok:
        return _emit(Result(ok=True, status="healthy", data=payload), args.json)
    return _emit(
        Result(
            ok=False,
            status="unhealthy",
            warnings=[str(v) for v in result.violations],
            data=payload,
        ),
        args.json,
        EXIT_ERROR,
    )


def cmd_memory_backup(args) -> int:
    """Mirror ``POST /api/memory/backup``: one consistent, private copy of
    the Memory database under ``<data-dir>/backups/``. The online SQLite
    backup API keeps the copy consistent while Memory is being written, and
    an earlier backup is never overwritten."""
    from .worlds.db import Database
    from .worlds.memory_store import MemoryError_, MemoryStore

    data_dir = Path(args.data_dir)
    db = Database.in_dir(data_dir)
    try:
        store = MemoryStore(db)
        path = store.backup(data_dir / "backups", actor="owner")
    except (MemoryError_, OSError) as exc:
        return _emit(
            Result(ok=False, status="unhealthy", warnings=[str(exc)]),
            args.json,
            EXIT_ERROR,
        )
    finally:
        db.close()
    return _emit(
        Result(
            ok=True,
            status="healthy",
            changed=True,
            data={"file": path.name},
        ),
        args.json,
    )


def cmd_memory_restore(args) -> int:
    """Wrap ``worlds.memory_store.restore_backup``: copy the Memory rows of
    one backup into a fresh data directory, validating every row. A target
    that already holds Memory is refused; restore never overwrites."""
    from .worlds.memory_store import MemoryError_, restore_backup

    data_dir = Path(args.data_dir)
    try:
        counts = restore_backup(Path(args.file), data_dir)
    except MemoryError_ as exc:
        return _emit(
            Result(ok=False, status="rejected", warnings=[str(exc)]),
            args.json,
            EXIT_ERROR,
        )
    return _emit(
        Result(
            ok=True,
            status="healthy",
            changed=True,
            data={"restored": counts, "data_dir": str(data_dir)},
        ),
        args.json,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="personal-world")
    p.add_argument("--data-dir", default="./data")
    p.add_argument("--config-dir", default="./config")
    sub = p.add_subparsers(dest="cmd", required=True)

    fw = sub.add_parser("framework", help="framework-level tooling")
    fw_sub = fw.add_subparsers(dest="framework_cmd", required=True)
    fw_v = fw_sub.add_parser(
        "validate", help="validate config against framework invariants"
    )
    fw_v.add_argument("--json", action="store_true")
    fw_v.set_defaults(fn=cmd_framework_validate)
    fw_vp = fw_sub.add_parser(
        "validate-packs",
        help="validate every participant pack under .project/participants/ "
        "(parse, required keys, schema namespace, id uniqueness)",
    )
    fw_vp.add_argument("--json", action="store_true")
    fw_vp.set_defaults(fn=cmd_framework_validate_packs)

    mem = sub.add_parser("memory", help="Memory backup and restore")
    mem_sub = mem.add_subparsers(dest="memory_cmd", required=True)
    mb = mem_sub.add_parser(
        "backup",
        help="write one consistent, private backup of Memory "
        "(mirrors POST /api/memory/backup)",
    )
    mb.add_argument("--json", action="store_true")
    mb.set_defaults(fn=cmd_memory_backup)
    mr = mem_sub.add_parser(
        "restore",
        help="copy the Memory rows of a backup into a fresh data directory "
        "(never overwrites an existing one)",
    )
    mr.add_argument("file", help="backup file to restore from")
    mr.add_argument("--json", action="store_true")
    mr.set_defaults(fn=cmd_memory_restore)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
