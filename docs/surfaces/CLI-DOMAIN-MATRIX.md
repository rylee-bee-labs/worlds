# CLI → DOMAIN/API MATRIX — Project Worlds

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the CLI ↔ domain/API parity map · **Read this if:** you need to know whether a CLI command has an API twin

**In short:** Maps each `personal-world` CLI command onto the domain/API surfaces it shares or parallels. The CLI shares core modules (world/registry/journal) but never calls the HTTP API.

The CLI shares core modules (world/registry/journal) but never calls
the HTTP API; "Domain/API IDs" lists the shared domain surfaces and
any API-parity endpoints.

| CLI ID | Domain/API IDs | Reads/Writes | Unique to CLI? |
|---|---|---|---|
| CLI-001 status | DOMAIN-001, DOMAIN-007 (parity: API-003) | Read world.json + registry | No (API parity) |
| CLI-002 daily | DOMAIN-002 (parity: API-004) | Read all providers; Write world.json+journal with --apply | No (API parity) |
| CLI-003 journal | JOURNAL-002 (parity: API-005) | Read journal.ndjson | No |
| CLI-004 actors | DOMAIN-007 (parity: API-014) | Read registry | No |
| CLI-005 settings-export | JOURNAL: export.py (parity: API-025) | Read world.json; Write stdout | No |
| CLI-006 world-export | export.py (parity: API-026) | Read world.json; Write stdout | No |
| CLI-007 story-export | JOURNAL-004 (parity: API-027) | Read journal.ndjson; Write stdout | No |
| CLI-008 backup [--apply] | export.py backup_payload (parity: API-028) | Read world+journal; Write file with --apply | Partial (CLI can write payload to file; API returns JSON only) |
| CLI-009 cement | WORLD-003 / DOMAIN-006 | Read+Write world.json (cement policy) | YES (only mutation path for cementing besides pack install) |
| CLI-010 init | LIFE-006 | Write world.json+journal (idempotent zero-provider) | YES (no API init route) |
| CLI-011 manifest | DOMAIN-007 (parity: API-015) | Read registry | No |
| CLI-012 prefs show/set | A11Y-001 (parity: API-030) | Read/Write world.json accessibility | No |
| CLI-013 changes | PROV-001 (parity: API-033) | Read git repos | No |
| CLI-014 history | PROV-001 (parity: API-034) | Read git repos | No |
| CLI-015 sync-status | PROV-001 (ahead/behind rollup) | Read git repos | Partial (API exposes via status entries; dedicated sync rollup is CLI-shaped) |
| CLI-016 framework validate | DOMAIN-003 | Read config/compose/exports | YES |
| CLI-017 framework validate-packs | DOMAIN-003 | Read .project/participants/ | YES |
| CLI-018 updates check/preview/apply/rollback/status | PROV-027/PROV-028, STORE-008 (parity: API-029 read-only) | Read compose; Write compose image tags + STORE-008 + journal | YES (apply/rollback deliberately CLI-only) |

> **Retired by ADR-0008:** the old CLI-019/CLI-020 backup/restore rows and the
> old `worlds_backup` module are gone with the old app. Memory backup/restore is
> **not** a CLI verb — it is the API route `POST /api/memory/backup` plus
> `personal_world.worlds.memory_store.restore_backup`. See
> [`docs/rebuild/DURABILITY.md`](../rebuild/DURABILITY.md).

Unique-to-CLI surfaces: cement (CLI-009), init (CLI-010), framework
validation (CLI-016/017), and update apply/rollback (CLI-018).

Unique-to-API surfaces (no CLI): chat, connections management, vault,
identity admin, apps, sections, memory search, reminders, discovery
writes, media, reconciler diff/propose, native-lab, ingress, journal
supersede, source-control refresh, projects status, brain templates,
principal profile, briefing, rooms/crew/doorways.