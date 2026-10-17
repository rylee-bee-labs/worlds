# MAJOR CALL CHAINS — Worlds

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the end-to-end call chains across the backend · **Read this if:** you want to trace how a feature travels from surface to store

**In short:** Compact, ID-linked traces of the main request paths — first launch, browser auth, world read/write, journal, reminders, chat, backup — plus the current rooms/briefing path. IDs resolve in `MASTER-SURFACE-REGISTRY.md`.

**Note (2026-09-26):** `UI-*` IDs below name the retired 2026-09-22 SPA (deleted `frontend/` tree); today's interface is `ui/` (the Bridge is home, reached through `GET /api/briefing`, `/api/rooms` and `/api/crew`). Backend chains are unchanged in shape.

Compact chains from the registry. IDs resolve in
MASTER-SURFACE-REGISTRY.md.

## Rooms, briefing and crew (current app, 2026-09-26)

```text
Bridge (ui/) → GET /api/briefing (API-085, require_auth + person)
→ briefing.py build_briefing: six fixed systems (agents/Workshop, estate/Engine room,
   records/Archive, interests/Observatory, news/Newsstand, threads/World tree);
   one failing source makes only its own system `unavailable` — never a 500
→ crew.py resolves the Keeper + each system's resident from the person's own crew
   (companion_id pref null → the one Assistant voice; pack off → «Worlds»)

GET /api/rooms (API-088) → rooms.py RoomsService
→ room list from Project Home GET /api/rooms/registry when PW_ROOMS_REGISTRY_URL is set
   (cached 60 s, last-known-good as rooms-registry.json); else fall back to PW_ROOMS
→ per room: GET /room, /room/cards, /room/needs-you (contract room/0)
   contract ∉ SUPPORTED_CONTRACTS={room/0} → `incompatible`; unreachable → `unreachable`
→ forward_principal: true also sends X-Worlds-Principal; cards/needs cached per person (15 s)

PUT /api/rooms/{id}/(visit|keeper|doorway) (API-088-*) → crew.json, per person
```

## First launch

```text
CLI-010 init → LIFE-006 init_world → STORE-001 world.json + STORE-002 journal.ndjson (zero-provider)
→ browser /setup (UI-010, NAV-003 AuthRoutes)
→ API-002 GET /api/setup/status (STORE-009 marker)
→ API-002 POST /api/setup → writes STORE-010 data/.env (PW_API_TOKEN) + STORE-009 + optional STORE-003 vault init
→ restart → AUTH-006 boot-token reconciliation (STORE-010 wins over compose env)
→ SPA (UI-013 via API-001 setup_needed → redirect)
```

## Browser auth (current reality, D1–D3)

```text
UI-011 login (token) → AUTH-009 POST /api/auth/login → AUTH-002 login_local (PW_API_TOKEN compare) → STORE-004 session + pw_session cookie
   (OIDC variant: AUTH-003 /api/auth/oidc/login → INT-006 exchange → login_oidc → STORE-004)
→ protected API calls resolve through the SAME seam: require_auth (AUTH-001)
   accepts either an Authorization: Bearer token OR the pw_session cookie
→ IDENT-003 resolve_principal / resolve_session_principal
   (single: bootstrap primary; multi: STORE-005 hashed tokens + local records)
→ request.state.principal → protected route
Step-up: require_step_up consumes the persisted, principal-bound session grant
   (AUTH-008, POST /api/auth/step-up), then true-loopback, then X-PW-StepUp
   (honored only with X-PW-Proxy-StepUp-Secret matching PW_PROXY_STEPUP_SECRET).
```

## World read

```text
UI-001/UI-012 → API-003 GET /api/status (AUTH-001)
→ LIFE-009 _state(): LIFE-002 build_registry (STORE-014 + STORE-015 merge → DOMAIN-007)
→ DOMAIN-001 World (STORE-001 load_world)
→ world.summary() + registry.status_map() + registry.actors()
```

## World brain write (propose → owner approval → execute)

```text
UI-008 Chat → API-010 POST /api/chat (AUTH-001)
→ CHAT-009/010 context (STORE-001, JOURNAL-002, CHAT-015 templates, CHAT-010 UI block)
→ CHAT-011 tool schemas → TOOL-000 loop (CHAT-004..008 provider)
   (only read + proposal tools are exposed; execution tools are blocked, tool_registry.py:96-127)
→ TOOL-024/025/026 propose_* → durable pending proposal in STORE (proposals.json, atomic)
→ [model turn ends; the model CANNOT approve or execute]

Owner approval path (human elevation):
→ API POST /api/proposals/{id}/approve (require_step_up) → approve_proposal
→ records approved_by/approved_at/approval_evidence → STORE (persisted) + JOURNAL-001 (approval)
→ API POST /api/proposals/{id}/execute (require_step_up)
→ TOOL-029 _execute_approved_write (checks status == "approved")
→ JOURNAL-001 journal.record(source=brain-tool) / WORLD-001/002 world mutation (MutationDenied gate)
→ save_world persists STORE-001 world.json; Scheduler persists STORE-006; proposal status persisted
```

## Journal

```text
UI-006 note → API-006 (AUTH-001 + person) → JOURNAL-001 record → STORE-002 journal.ndjson
→ LIFE-008 NativeMemoryProvider.index_journal → STORE-012 memory.fts5.db (derived)
→ API-016 search (derived) | TOOL-004 search (direct journal.search)
UI-006 correction → UI approval → API-007 supersede (step-up) → JOURNAL-003 supersede (append-only link) → STORE-002
CLI-007/API-027 → JOURNAL-004 StoryRenderer; API-009 → JOURNAL-005 AuditRenderer
```

## Project status

```text
UI-004 Projects → API-079 GET /api/projects/status (AUTH-001)
→ PROV-026 AgentSyncProjectSensor → INT-001 agent-sync subprocess (`agent-sync status --all --format json`)
→ normalized play-nice/repo-status-v1 records + freshness
→ UI
(git layer: UI-004 → API-033/034 → PROV-001 NativeGit → INT-005 git subprocess → repos)
(approved act: UI-004 → API-035 refresh (step-up) → repository_status → JOURNAL-001 PROVIDER_ACTION)
(remote facts: UI-004 → API-036 → PROV-004 GitHubEnrichment → INT-002 gh CLI)
```

## Reminder

```text
UI/API write → API-067 POST/PATCH/DELETE (step-up) → LIFE-004 Scheduler.add/toggle/remove → STORE-006 reminders.json
read → API-067 GET → Scheduler.list_reminders (instance)
read (chat) → TOOL-019 inspect_reminders → wired Scheduler (no parallel file read)
fire → LIFE-004 scheduler thread check_and_fire → JOURNAL-001 observation
```

## Chat

```text
UI-008 ChatRoute/ChatPanel → API-010 POST /api/chat (AUTH-001)
→ context: CHAT-009 build_world_context (+ CHAT-015 TemplateRegistry surface instructions + CHAT-010 UI context)
→ provider: DOMAIN-007 provider_for("reasoning") → CHAT-004..008
→ tools: TOOL-000 schemas; loop executes read tools via tool_registry handlers
→ reply: CHAT-013 extract_proposal (journal correction proposal validated vs JOURNAL-002)
→ JOURNAL-001 recommendation event (source=chat)
```

## Backup

Two distinct paths, do not conflate them:

```text
ordinary share/export
CLI-008 backup [--apply] / API-028 GET /api/backup (AUTH-001)
→ export.backup_payload(DOMAIN-001 world, JOURNAL-002 journal)
→ includes: serialized world + journal (incl. private state)
→ excludes: STORE-003 vault.enc, STORE-005 users, STORE-004 sessions, STORE-006 reminders, STORE-007 apps,
   per-user trees, STORE-015 connections.local.json, STORE-013/018/019
→ external encryption expected (SOPS/age), not provided by the app

full-instance Memory backup (durable; not encrypted at rest) — docs/rebuild/DURABILITY.md
POST /api/memory/backup (owner, CSRF)
→ memory_store.backup (SQLite online backup API) → $PW_DATA_DIR/backups/worlds-YYYYMMDD-HHMMSS.db (0600)
→ covers Memory (kept/later/records/history), including locked rows and session/token hashes
restore: stop Worlds → memory_store.restore_backup(<file>, <data dir>)
→ copies ONLY Memory rows into a freshly migrated worlds.db, validates row by row, rebuilds the find index,
   refuses a non-empty target; sessions/tokens/authorizations are never imported
```

## Vault value read (exceptional workflow)

```text
UI-007 unlock → API-062 (bearer) → SECRET-001 Vault.unlock (SECRET-003 Fernet/PBKDF2; without the crypto extra it fails closed — `unavailable`, no fallback)
→ API-064 GET /api/vault/{name} (bearer + AUTH-005 loopback/private check)
→ STORE-003 → value returned → JOURNAL-001 name-only audit entry
```

## Connection save

```text
UI-021 → API-021 PUT (AUTH-001 + in-handler require_step_up) → CONN-002 ConnectionManager
→ writes STORE-015 connections.local.json (tracked file never written)
→ next request rebuilds: LIFE-002 build_registry merges STORE-014 + STORE-015 → DOMAIN-006 provider slots
```