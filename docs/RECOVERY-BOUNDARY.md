# Recovery boundary — moved to the rebuild

> **Superseded by [ADR-0008](adr/0008-front-door.md) and the rebuild durability canon (2026-10-01):** the old app and its whole-instance encrypted archive were replaced. The live recovery boundary is now [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md); the drill that measures it is [scripts/restore-drill.sh](../scripts/restore-drill.sh). This page is kept only so old links resolve.

> **Status:** Historical · **Verified:** 2026-10-02 · **Canonical for:** nothing (see [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md)) · **Read this if:** an old link sent you here, or you are writing recovery/backup docs.

**In short:** recovery is now per [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md): config files and `worlds.db` are durable and are backed up; the cache is disposable. Memory backup and restore are the only app-level paths.

## New canon

| Concern | Where it lives now |
| --- | --- |
| What survives a container rebuild, what to back up | [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md) — three classes: config (`$PW_CONFIG_DIR`), database (`$PW_DATA_DIR/worlds.db`), disposable cache |
| Configuration and identity | `$PW_CONFIG_DIR/owner.yaml` and `$PW_CONFIG_DIR/worlds/…` — [docs/rebuild/CONTRACTS.md](rebuild/CONTRACTS.md) C1/C7 |
| Memory backup | `POST /api/memory/backup` → a dated `$PW_DATA_DIR/backups/worlds-*.db` copy through SQLite's online backup API (file 0600, directory 0700). It is not encrypted by the app — keep it as private as the database. |
| Memory restore | Stop Worlds, then `python -c "from personal_world.worlds.memory_store import restore_backup; print(restore_backup('<backup file>', '<data dir>'))"`. It copies only Memory rows into a freshly migrated database, validates row by row, rebuilds the find index, and refuses a target that already holds Memory. |
| Measured drill | [scripts/restore-drill.sh](../scripts/restore-drill.sh) — seed through the real API → backup through the real route → refusal checks → restore into a fresh data dir → boot the front-door app (`personal_world.worlds.production:app_from_env`) → read the same rows back through the API |
| Framework gate | `personal-world framework validate --json` |

## What this page used to cover

This page carried the dated 2026-09-21 measured result of the retired app's whole-instance encrypted archive: its timings, the covered/not-covered boundary, and three defects that drill found. That archive and its backup/restore CLI were removed with the old app (ADR-0008). The dated evidence is preserved in the retired app's git history, not as current truth.

The current durability and recovery boundary is [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md). The current measured drill is [scripts/restore-drill.sh](../scripts/restore-drill.sh).
