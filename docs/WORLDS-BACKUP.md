# Worlds backup & restore — moved to the rebuild

> **Superseded by [ADR-0008](adr/0008-front-door.md) and the rebuild durability canon (2026-10-01):** the old app and its whole-instance encrypted archive were replaced. Backup and restore are now the Memory paths in [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md); this page is kept only so old links resolve.

> **Status:** Historical · **Verified:** 2026-10-02 · **Canonical for:** nothing (see [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md)) · **Read this if:** an old link sent you here.

**In short:** this page described the old app's encrypted archive of a whole instance. The front-door rebuild (ADR-0008) replaced that with two durable classes — config files and the Memory database — backed up and restored per [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md).

## New canon

- **Durability classes:** config (`$PW_CONFIG_DIR`), database (`$PW_DATA_DIR/worlds.db`), disposable cache — [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md).
- **Memory backup:** `POST /api/memory/backup` writes a dated `$PW_DATA_DIR/backups/worlds-*.db` copy (SQLite online backup API; file 0600, directory 0700) and records a `backup` event in History.
- **Memory restore:** stop Worlds, then `python -c "from personal_world.worlds.memory_store import restore_backup; print(restore_backup('<backup file>', '<data dir>'))"`. Sessions, agent tokens and authorizations are never imported, so everyone signs in again after a restore.
- **Measured drill:** [scripts/restore-drill.sh](../scripts/restore-drill.sh).
- **App entrypoint:** `uvicorn personal_world.worlds.production:app_from_env --factory`.
- **Framework gate:** `personal-world framework validate --json`.

## What this page used to cover

The retired whole-instance archive, its format, its passphrase rules, its HTTP routes and its threat notes belonged to the old app. They are not part of the front-door product and no current procedure uses them. The old text is preserved in git history.

Do not follow the retired archive procedure. Back up the config and data volumes — or use the Memory route above — per [docs/rebuild/DURABILITY.md](rebuild/DURABILITY.md).
