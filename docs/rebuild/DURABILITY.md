# Durability classes (rebuild, C4)

> **Status:** Accepted 2026-10-01 · **Canonical for:** what survives a container rebuild, what to back up, and how to restore it · **Read this if:** you deploy, back up or restore Worlds.

**In short:** three classes. Config files and `worlds.db` are durable and are backed up; the cache is disposable. Memory is durable from day one.

| Class | Where | Holds | Back up? | Lose it and... |
| --- | --- | --- | --- | --- |
| Config (canonical) | `$PW_CONFIG_DIR` (`worlds/…/*.yaml`, `owner.yaml`) | providers, requests, cards, boards, actions, owner identity | yes, with the config volume | Worlds shows nothing configured; no data is lost |
| Database (durable) | `$PW_DATA_DIR/worlds.db` | Memory (kept, later, records, history, find index), authorizations and receipts, sessions, agent-token hashes | yes: the Memory backup below, plus the volume | Memory and the audit trail are gone |
| Keys (durable) | `$PW_DATA_DIR/csrf.key`, `oidc-flow.key` (0600) | CSRF and OIDC flow signing keys | with the data volume | everyone signs in again; nothing else |
| Cache (disposable) | `$PW_DATA_DIR/cache/` | last-good card data | no | cards show `unknown` until the next successful fetch |

## Memory

- `worlds.db` lives on a **volume**, never in the container's writable layer. The container is replaceable; the volume is not.
- **Export:** `GET /api/memory/export/{kept|later|records|history}` streams NDJSON, one JSON object per line. Locked records are included only with the owner's fresh step-up. Every export is written to History.
- **Backup:** `POST /api/memory/backup` makes `$PW_DATA_DIR/backups/worlds-YYYYMMDD-HHMMSS.db` through SQLite's online backup API (consistent while Worlds is writing; mode 0600, directory 0700; an existing file is never overwritten) and writes a `backup` event to History. A backup contains everything in `worlds.db` including locked records and session/token hashes (those are not restored): keep it as private as the database.
- **Restore:** stop Worlds, then `python -c "from personal_world.worlds.memory_store import restore_backup; print(restore_backup('<backup file>', '<data dir>'))"`. The backup is treated as untrusted: it is opened read-only (no trigger or view in it can run), checked with `PRAGMA integrity_check`, and ONLY its Memory rows (kept, later, records, history) are copied, validated row by row (a restored history row's `actor`/`event` are untrusted display text only: bounded, kept opaque, never parsed or trusted), into a freshly migrated database in one transaction (a bad row refuses the whole restore); the find index is rebuilt. The restored `worlds.db` (and its `-wal`/`-shm` siblings) is created mode 0600 without changing the process umask. Sessions, agent tokens, authorizations, executions and any schema object in the backup are never imported, so after a restore everyone signs in again and agent tokens are re-issued. A data directory that already holds Memory is refused (restore never overwrites). Start Worlds against that data dir.
- Old Worlds data is **not** imported (owner decision 2026-10-01); the old backups stay where they are until retirement.

## Known edge: interrupted-action recovery

Recovery turns an interrupted action into UNKNOWN (nothing is ever re-sent) once its owner's lease is gone. Two containers that share a volume **and** use host networking (same kernel boot id, both pid 1, same host name) cannot be told apart by identity; each is treated as alive until its lease expires (30 s). The cost is a delay in settling an interrupted row, never a repeat dispatch. Accepted 2026-10-01.

## Known edge: interrupted-action recovery

Recovery turns an interrupted action into UNKNOWN (nothing is ever re-sent) once its owner's lease is gone. Two containers that share a volume **and** use host networking (same kernel boot id, both pid 1, same host name) cannot be told apart by identity; each is treated as alive until its lease expires (30 s). The cost is a delay in settling an interrupted row, never a repeat dispatch. Accepted 2026-10-01.
