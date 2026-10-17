# TOOL → DOMAIN MATRIX — Project Worlds

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the brain's registered tools and how they read/write · **Read this if:** you need to know what a model can inspect or propose

**In short:** Every tool the brain can call, whether it reads or proposes a write, and which domain/store it touches. The model can propose but never approve or execute.

Code-observed count: **32 registered tools (as of 2026-09-26)** — `GET /api/tools`
is the live list; TOOL-000 is the container. The extraction below is numbered for
the 2026-09-14/17 set, so later additions keep their names, not a new number.

| Added since the extraction (2026-09-26) | Read/Write | Domain target |
|---|---|---|
| `list_content`, `list_content_repos`, `search_content` | Read | `providers/content_db.py` (content database) |

**Note:** `tool_registry.py:NNN` line numbers below are from the 2026-09-17 pass
and may have drifted; find the named tool instead.

| Tool ID | Read/Write | Proposal? | Approval? | Executor | Domain target | State |
|---|---|---|---|---|---|---|
| TOOL-001 inspect_world_status | Read | No | No | world.summary() | DOMAIN-001 | ACTIVE |
| TOOL-002 inspect_manifest | Read | No | No | registry.manifest() | DOMAIN-007 | ACTIVE |
| TOOL-003 read_journal | Read | No | No | journal.recent | JOURNAL-002 | ACTIVE |
| TOOL-004 search_journal | Read | No | No | journal.search | JOURNAL-002 | ACTIVE |
| TOOL-005 inspect_source_control | Read | No | No | status_all | PROV-001 | ACTIVE |
| TOOL-006 inspect_source_control_history | Read | No | No | repository_history | PROV-001 | ACTIVE |
| TOOL-007 inspect_projects | Read | No | No | AgentSyncProjectSensor | PROV-026 | ACTIVE |
| TOOL-008 inspect_lab_inventory | Read | No | No | NativeLabInventory.observe | PROV-012 | ACTIVE |
| TOOL-009 inspect_lab_health | Read | No | No | NativeLabHealth.observe | PROV-012 | ACTIVE |
| TOOL-010 inspect_lab_resources | Read | No | No | NativeLabResources.observe | PROV-012 | ACTIVE |
| TOOL-011 inspect_lab_settings | Read | No | No | NativeLabSettings.observe | PROV-012 | ACTIVE |
| TOOL-012 inspect_reconciler_status | Read | No | No | NativeSettingsReconciler.observe | PROV-014 | ACTIVE |
| TOOL-013 inspect_reconciler_diff | Read | No | No | reconciler._desired (no observed diff) | PROV-014 | PARTIAL |
| TOOL-014 inspect_discovery_status | Read | No | No | NativeDiscovery.observe | PROV-013 | ACTIVE |
| TOOL-015 list_discovery_sources | Read | No | No | discovery.observe | PROV-013 | ACTIVE |
| TOOL-016 list_interests | Read | No | No | discovery.observe | PROV-013 | ACTIVE |
| TOOL-017 run_discovery | Read-labeled (fetches external content; saves feedback) | No | No | discovery.discover | PROV-013 | ACTIVE (write side-effect mislabeled read) |
| TOOL-018 inspect_vault_status | Read | No | No | vault.is_unlocked | STORE-003 (lock state only) | ACTIVE |
| TOOL-019 inspect_reminders | Read | No | No | direct reminders.json read (env PW_DATA_DIR) | STORE-006 (bypasses Scheduler) | ACTIVE (duplicate path) |
| TOOL-020 inspect_media_status | Read | No | No | engine.status | PROV-015 | ACTIVE |
| TOOL-021 inspect_media_recent | Read | No | No | engine.recent | PROV-015 | ACTIVE |
| TOOL-022 inspect_media_activity | Read | No | No | engine.activity | PROV-015 | ACTIVE |
| TOOL-023 search_media | Read | No | No | engine.search | PROV-015 | ACTIVE |
| TOOL-024 propose_journal_entry | Write | Yes (durable `proposals.json`) | Server-held: owner approves via step-up API | _execute_approved_write → journal.record(source=brain-tool) | JOURNAL-001 | ACTIVE |
| TOOL-025 propose_world_intent | Write | Yes | Same as above | _execute_approved_write → world.set_intent | WORLD-002 | ACTIVE |
| TOOL-026 propose_world_fact | Write | Yes | Same as above | _execute_approved_write → world.record_fact | WORLD-001 | ACTIVE |
| TOOL-027 propose_reminder | Write | Yes | Server-held owner approval | executor writes through wired `Scheduler.add` (`tool_registry.py:799-817`) | STORE-006 | ACTIVE (persists via Scheduler; D1–D3) |
| TOOL-028 propose_reconciler_apply | Write | Yes | Server-held owner approval | returns `unsupported`; proposal left `pending`, nothing applied (`tool_registry.py:819-830`) | PROV-014 | PARTIAL (unsupported; no adapter yet) |
| TOOL-029 execute_approved_write | Write | No (is the executor) | Server-side check: `status == "approved"` only; no model-supplied boolean | durable `proposals.json` (atomic); execution only via step-up API (`api.py:979-1004`) | JOURNAL-001 / WORLD-001 / WORLD-002 | ACTIVE (execution structurally blocked from the model, `tool_registry.py:96-127`) |

Cross-cutting observations (reality, not fixes):

- Write proposals are durable and server-held: `configure_proposal_store`
  persists `data/proposals.json` atomically after every state change
  (`tool_registry.py:574-615`). Approval is established ONLY through the
  step-up API (`approve_proposal`, `:846-885`) and records
  `approved_by`/`approved_at`/`approval_evidence`; the model cannot approve
  or execute. Restarts restore pending/approved state. (Remaining:
  proposals are instance-global; no frontend review UI.)
- TOOL-017 (`run_discovery`) is registered read_write="read" while it
  fetches external content and can persist feedback to
  discovery.json.
- TOOL-019 reads reminders through a wired `Scheduler`
  (`tool_registry.py:1154-1168`), not a parallel file read; with no
  scheduler it answers `unavailable`.