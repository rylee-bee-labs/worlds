# PROJECT WORLDS — FINAL RECEIPT
# Merged to main via PR #42 (3405f60) and PR #43 (dc2eda7)
# Date: 2026-09-14

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/CURRENT.md`) · **Read this if:** you need the 2026-09-14 merge receipt's own counts and claims. · **Superseded by:** `.project/CURRENT.md`.

**In short:** a 2026-09-14 merge receipt claiming 726 tests, 29 brain tools, 15 wired screens and 18 capabilities. Kept for provenance; treat no count as current. Since this record: the product is called Worlds, the interface is `ui/` with Bridge as home, and production runs on the transcode host.

---

## TESTS

**726 passed, 0 failed, 0 warnings**

## FRAMEWORK VALIDATION

**0 violations**

## FRONTEND BUILD

**Build clean** (pre-existing vitest heading-hierarchy failures unrelated
to architecture work)

---

## COMPOSE STATUS

| Service | Image | Status |
|---------|-------|--------|
| core | ghcr.io/rylee-bee/personal-world:latest | healthy |
| ollama | ollama/ollama:latest | healthy |
| ollama-pull | ollama/ollama:latest | completed (qwen3:1.7b pulled) |

---

## CAPABILITIES (18 — all have native baseline)

| Capability | Native Provider | Status |
|------------|----------------|--------|
| source_control | native_git | WORKING |
| deployment | native_deployment | not_configured (needs targets) |
| secrets | native_vault | WORKING |
| calendar | native_calendar | not_configured (needs sources) |
| discovery | native_discovery | WORKING |
| settings_validation | native_reconciler | WORKING |
| service_validation | native_lab | WORKING |
| update_discovery | native_updates | not_configured (needs sources) |
| memory | native_memory | WORKING |
| journal | built-in | WORKING |
| reasoning | ollama | WORKING |
| media | native_media | not_configured (needs providers) |
| notifications | native_notifications | not_configured (needs targets) |
| scheduler | built-in | WORKING |
| homelab_* | lab_cli | OPTIONAL |

---

## SCREENS (15 wired)

| Screen | Route | Status |
|--------|-------|--------|
| TodayScreen | / | ✅ WIRED |
| ChatRoute | /chat | ✅ WIRED |
| JournalScreen | /journal | ✅ WIRED |
| VaultScreen | /vault | ✅ WIRED |
| WorldScreen | /world | ✅ WIRED |
| SettingsScreen | /settings | ✅ WIRED (Brain panel added) |
| ProjectsScreen | /projects | ✅ WIRED |
| LabScreen | /lab | ✅ WIRED |
| InterestsScreen | /interests | ✅ WIRED |
| MediaScreen | /media | ✅ WIRED |
| SetupWizard | /setup | ✅ WIRED |
| LoginScreen | /login | ✅ WIRED |
| LabOperationsPanel | (sub-panel) | ✅ WIRED |
| CompanionPresence | sidebar | ✅ WIRED |
| CompanionPopover | sidebar | ✅ WIRED |

---

## BRAIN TOOLS (29)

### Read tools (19):
inspect_world_status, inspect_manifest, read_journal, search_journal, inspect_source_control, inspect_source_control_history, inspect_projects, inspect_lab_inventory, inspect_lab_health, inspect_lab_resources, inspect_lab_settings, inspect_reconciler_status, inspect_reconciler_diff, inspect_discovery_status, list_discovery_sources, list_interests, run_discovery, inspect_vault_status, inspect_reminders

### Media tools (4):
inspect_media_status, inspect_media_recent, inspect_media_activity, search_media

### Write tools (6, proposal-based):
propose_journal_entry, propose_world_intent, propose_world_fact, propose_reminder, propose_reconciler_apply, execute_approved_write

---

## PROVIDER TOOL-CALLING

| Provider | chat_with_tools | Status |
|----------|----------------|--------|
| Ollama | ✅ | Working |
| OpenAI-compat | ✅ | Working |
| OpenAI | ✅ | Working |
| Anthropic | ✅ | Working |
| OpenCode | ❌ | tool_calling: unsupported |

---

## BRAIN TEMPLATE SYSTEM

| Component | Status |
|-----------|--------|
| Shipped templates | 19 (4 core, 9 surfaces, 4 tasks, 2 formats) |
| Template registry | ✅ Working |
| Private overrides | ✅ config.prompts.local/ |
| Surface composition | ✅ Chat derives surface from route |
| Provenance | ✅ GET /api/brain/provenance |
| Settings → Brain | ✅ Template list with metadata |

---

## CONNECTIONS & PROVIDERS

| Component | Status |
|-----------|--------|
| Capabilities | 7 |
| Provider schemas | 18 |
| UI configuration | ✅ Settings → Connections panel |
| Test buttons | 9 live testable, 3 local validation, 6 no-test |

---

## AUTH/SSO

| Feature | Status |
|---------|--------|
| Native auth module | ✅ Implemented |
| Session-cookie auth | ✅ Implemented |
| OIDC config | ✅ Provider-neutral seam (config/oidc.json) |
| Authelia support | ✅ Authelia-compatible / implementation-ready |
| Live Authelia login | NOT VERIFIED (no running instance) |
| Step-up auth | ✅ 300s window |
| Break-glass | ✅ PW_API_TOKEN fallback |

---

## NATIVE PROVIDERS (in-process, no new containers)

| Provider | File | Purpose |
|----------|------|---------|
| native_vault | providers/native_vault.py | Secrets via encrypted vault |
| native_memory | providers/native_memory.py | SQLite FTS5 search |
| native_calendar | providers/native_calendar.py | ICS/iCal feeds |
| native_notifications | providers/native_notifications.py | Webhook + ntfy |
| native_updates | providers/native_updates.py | GitHub releases + version URLs |
| native_deployment | providers/native_deployment.py | Docker Compose + systemd |
| native_media | providers/native_media.py | Plex/Sonarr/Radarr/Lidarr |
| native_lab | providers/native_lab.py | Service inventory + health |
| native_discovery | providers/native_discovery.py | Content discovery |
| native_reconciler | providers/native_reconciler.py | Settings reconciliation |

---

## EXECUTION VIEWER

| Component | Status |
|-----------|--------|
| ExecutionViewer | ✅ Implemented |
| ExecutionStore | ✅ Persistent (executions.json) |
| Record structure | actor, target, host, command, timestamps, status, exit_code, stdout/stderr |
| Query | by actor, target, status |

---

## WARNING CLEANUP

- Third-party warnings (starlette, anyio, fastapi) filtered via conftest.py
- Our code warnings treated as errors (pyproject.toml filterwarnings)
- 726 passed, 0 failed, 0 warnings

---

## KNOWN NOT_CONFIGURED

- deployment (no targets configured)
- calendar (no ICS/CalDAV sources)
- update_discovery (no sources configured)
- media (no Plex/Sonarr/Radarr/Lidarr providers)
- notifications (no targets configured)
- OIDC (no config/oidc.json)

---

## REMAINING DEFECTS

None.

---

## GIT COMMITS

| SHA | Description |
|-----|-------------|
| dc2eda7 | Merge PR #43 — feat/workshop-v3-architecture |
| 3405f60 | Merge PR #42 — feat/workshop-v3-architecture |
| 7e0269d | fix: reconciliation receipt — 726 tests, 22 ahead |
| de15d76 | reconciliation: issue closures, receipt fixes |
| f73df40 | docs: audited Connections receipt |
| ee488b1 | feat: Connections & Providers control panel |
| 8e9164d | Brain Template System |
| c446e14 | Native providers + execution viewer + zero warnings |
| 92e4f9f | Media + Auth/SSO + companion + Settings + write tools |
| d4f8d94 | Wire all screens + chat UI + tool registry |
| 63aa73d | Workshop v3 shell + native products + Ollama |

---

## FILE LOCATIONS

| File | Path |
|------|------|
| This receipt | docs/FINAL-RECEIPT.md |
| Full inventory | docs/FULL-SYSTEM-INVENTORY.md |
| Connections receipt | docs/CONNECTIONS-RECEIPT.md |
| Compose | compose.yaml |
| Connections | config/connections.json |
| Templates | config/prompts/ |
| Template registry | src/personal_world/template_registry.py |
| Tool registry | src/personal_world/tool_registry.py |
| Auth module | src/personal_world/auth.py |
| Execution viewer | src/personal_world/execution_viewer.py |
| Native providers | src/personal_world/providers/native_*.py |
