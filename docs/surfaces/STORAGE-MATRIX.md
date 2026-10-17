# STORAGE MATRIX — Worlds

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the on-disk stores and what backs up · **Read this if:** you need to know where a piece of state lives and whether the backup covers it

**In short:** Every durable and derived store, its path, who reads and writes it, and whether the backup covers it. Rows added 2026-09-26 cover the rooms registry and per-person crew.

Paths are relative to `PW_DATA_DIR` (default `./data`) and
`PW_CONFIG_DIR` (default `./config`) unless absolute.

| Store ID | Path | Authoritative? | Readers | Writers | Backup? | Rebuildable? |
|---|---|---|---|---|---|---|
| STORE-001 | data/world.json | YES (world model) | everything (per-request load_world) | save_world, CLI init, CLI cement, setup | backup_payload yes (world payload) | via init + exports (facts/intents/policies/lore restored only manually) |
| STORE-002 | data/journal.ndjson | YES (append-only events) | Journal, NativeMemoryProvider, story/audit renderers, chat context | Journal.record/supersede, every surface | backup_payload yes | no (primary evidence) |
| STORE-003 | data/vault.enc | YES (secrets) | Vault, NativeVaultProvider | Vault set/delete; setup (init) | NO (deliberately excluded from backup_payload) | no (encrypted; passphrase required) |
| STORE-004 | data/sessions.json | YES (browser sessions) | AuthManager/SessionStore | SessionStore create/invalidate/step-up | NO | yes (sessions are ephemeral) |
| STORE-005 | data/users.json | YES (identity records) | IdentityStore, AUTH-001 multi mode, admin routes | identity admin API, display-name PUT | NO | no (hashed tokens) |
| STORE-006 | data/reminders.json | YES (reminders) | Scheduler, API-067, TOOL-019 (direct read — duplicate path) | Scheduler add/remove/toggle, API-067 | NO | partially (re-created by use) |
| STORE-007 | data/apps.json | YES (apps launcher) | API-066 | PUT /api/apps | NO | yes (user data, re-creatable) |
| STORE-008 | data/updates-session.json | YES (update session state) | UpdateManager, API-029, CLI-018 | apply/rollback journaling | NO | yes (session state) |
| STORE-009 | data/setup-complete | YES (first-run marker) | healthz, setup status, setup POST, UI gate | POST /api/setup | NO | no (deleting re-arms setup) |
| STORE-010 | data/.env (PW_API_TOKEN=…) | YES (setup-created token wins at boot) | _reconcile_boot_token | POST /api/setup | NO | no (credential) |
| STORE-012 | data/memory.fts5.db | derived only | NativeMemoryProvider.search, API-016 | index_journal (auto) | NO | YES (reindexed from journal.ndjson) |
| STORE-013 | data/theme-packs/ | YES (pack manifests) | ThemePackRegistry, API-065 | manual placement | NO | yes (user-supplied) |
| STORE-014 | config/connections.json | YES (tracked provider wiring, no secrets) | build_registry, ConnectionManager, API-080 rollups (direct read) | manual edit (API writes go to local) | NO | yes (documented example) |
| STORE-015 | config/connections.local.json | YES (private overrides) | build_registry merge, ConnectionManager._read_local | ConnectionManager writes | NO | no (private) |
| STORE-016 | config/prompts/ (+ prompts.local) | YES (shipped brain templates + overrides) | TemplateRegistry | manual | NO | yes (shipped defaults) |
| STORE-017 | config/oidc.json | YES (OIDC config) | AuthManager | manual | NO | yes (re-configure) |
| STORE-018 | ~/.config/personal-world/discovery.json | YES (discovery sources/interests) | NativeDiscovery | add_source/add_interest, discover feedback | NO | yes (user data, re-enterable) |
| STORE-019 | ~/.config/personal-world/reconciler/desired/ | YES (desired state YAML/JSON) | NativeSettingsReconciler | manual only | NO | yes (user-authored) |
| STORE-020 | data/executions.json | derived (execution viewer) | ExecutionStore.query | ExecutionStore append/update | NO | YES (append log; currently orphaned) |
| STORE-021 | data/users/<id>/ (multi mode) | YES (per-person world/journal) | _user_paths | same as STORE-001/002 per person | backup_payload covers GLOBAL world only | partially |
| STORE-022 | data/rooms-registry.json | YES (last-known-good room list) | RoomsService (registry read), `/api/rooms` | registry fetch (atomic) | NO | yes (re-fetched from Project Home) |
| STORE-023 | data/rooms-state.json | YES (per-room keeper/doorway + visit state) | RoomsService, `/api/rooms` | `/api/rooms/{id}/(visit\|keeper\|doorway)` | NO | partially (per-person state; re-choosable) |
| STORE-024 | crew.json via `identity.principal_scoped_path` (`data/crew.json` single · `data/users/<id>/crew.json` multi) | YES (per-person crew/keepers/doorways) | crew.py, briefing.py, `/api/crew` | `/api/crew*`, keeper/doorway PUT | NO | partially (per-person; re-createable) |
| — | data/.env also read at boot for PW_API_TOKEN (see STORE-010) | — | — | — | — | — |

Notes:

- `backup_payload` includes world + journal only. vault.enc, users,
  sessions, apps, reminders, per-user trees, connections.local.json,
  theme packs, discovery.json, and reconciler desired state are NOT in
  any automated backup; recovery plans must cover them separately
  (matches ARCHITECTURE.md export contract).
- The **full-instance SOS archive** of the retired app is gone (ADR-0008).
  Backup is now the config volume plus the Memory database: `POST
  /api/memory/backup` writes a dated `worlds.db` copy under
  `$PW_DATA_DIR/backups/`, and `restore_backup` imports Memory rows into an
  empty data dir. See [`docs/rebuild/DURABILITY.md`](../rebuild/DURABILITY.md).
- All four export contracts (settings/world/story/backup) are
  serialization views, never the storage of record.
- `config/connections.json` is tracked and must stay secret-free;
  `tests/test_public_safety.py` is the regression gate.