# Project Worlds — API Wiring Handoff (Final)
# Every endpoint accounted for. Nothing forgotten.

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/CURRENT.md`) · **Read this if:** you need the 2026-09-13 endpoint-disposition handoff (68 endpoints, 19 read tools). · **Superseded by:** `.project/CURRENT.md`.

**In short:** a 2026-09-13 handoff classifying every endpoint as UI-wired, tool-wired, internal, gap or deferred, with 68 endpoints and 19 read tools. Kept for provenance; treat no count as current. Since this record: the product is called Worlds and many of these surfaces have since been built out or retired.

---

## Endpoint Disposition

### Legend
- **UI WIRED** — endpoint → hook → screen renders it
- **TOOL WIRED** — endpoint → tool handler → brain can invoke at runtime and receive structured Result
- **UI + TOOL** — both
- **INTERNAL** — used by infrastructure, no UI/tool needed
- **API GAP** — endpoint exists but no UI/tool; reason documented
- **DEFERRED** — intentionally not wired; reason documented

### TOOL WIRED means
The model can actually invoke this operation at runtime via Ollama function-calling
and receive its structured Result. Not merely "the model was told about it in its
system prompt." The execution flow is:

```
User request → Qwen3 1.7B → selects registered tool → Project Worlds tool registry
→ existing domain operation → structured Result → Qwen explains result
```

---

## Tool-Calling Architecture

### Read tools (execute immediately)
These are exposed via Ollama function-calling. The model selects a tool,
Project Worlds executes it against the same domain operations the HTTP API uses,
and returns structured truth. The model then explains the result.

| Tool ID | Capability | What it does |
|---------|-----------|--------------|
| `inspect_world_status` | world | Facts, intents, policies, lore, capabilities |
| `inspect_manifest` | manifest | Capability manifest with native/provider status |
| `read_journal` | journal | Recent journal entries |
| `search_journal` | journal | Text search across journal |
| `inspect_source_control` | source_control | Repos with branch, revision, dirty state |
| `inspect_source_control_history` | source_control | Commit history for a repo |
| `inspect_projects` | projects | Agent-sync project estate |
| `inspect_lab_inventory` | lab | Native lab service inventory |
| `inspect_lab_health` | lab | Health summary |
| `inspect_lab_resources` | lab | CPU, memory, disk |
| `inspect_reconciler_status` | reconciler | Services with desired state |
| `inspect_discovery_status` | discovery | Sources, interests, items count |
| `list_discovery_sources` | discovery | Configured sources |
| `list_interests` | discovery | Configured interests |
| `run_discovery` | discovery | Fetch new content |
| `inspect_vault_status` | vault | Lock state (never secrets) |
| `inspect_reminders` | reminders | Active reminders |

### Write tools (not yet exposed)
Write tools require propose → approval → execution → evidence.
Not given to the model until the action/approval framework is ready.

### Chat flow
```
POST /api/chat
  ↓
Build world context + tool schemas
  ↓
Ollama chat_with_tools(messages, tools)
  ↓
If tool_calls returned:
  Execute each tool via registry.invoke()
  Add tool results to messages
  Continue loop (max 3 rounds)
If text response returned:
  Return to user
```

---

### Core / Auth / Setup

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/healthz` | GET | INTERNAL | — | — | Docker healthcheck |
| `/api/setup/status` | GET | UI WIRED | Setup wizard | — | One-time use |
| `/api/setup` | POST | UI WIRED | Setup wizard | — | One-time use |

### World / Status

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/status` | GET | UI + TOOL | Today, World, Settings | inspect_world_status | Core status |
| `/api/daily` | GET | UI WIRED | Today | — | Daily digest |
| `/api/daily` | POST | UI WIRED | Today (button) | — | Run daily loop |
| `/api/actors` | GET | UI + TOOL | World | inspect_actors | Provider directory |
| `/api/manifest` | GET | UI + TOOL | World (disclosure) | inspect_manifest | Capability manifest |
| `/api/updates` | GET | DEFERRED | — | — | No update surface yet |

### Journal / Memory

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/journal` | GET | UI + TOOL | Today, Journal | read_journal | Recent entries |
| `/api/journal` | POST | UI WIRED | Journal (form) | — | Write entry |
| `/api/journal/supersede` | POST | UI WIRED | Journal (via proposal) | — | Correction |
| `/api/journal/history` | GET | UI WIRED | Journal (disclosure) | — | Full history |
| `/api/journal/audit` | GET | UI WIRED | Journal (disclosure) | — | Audit trail |
| `/api/memory/search` | GET | UI + TOOL | Journal (search) | search_journal | Semantic search |

### Prefs / Sections / Reminders

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/prefs` | GET | UI WIRED | Settings | — | Read prefs |
| `/api/prefs` | PUT | UI WIRED | Settings | — | Write prefs |
| `/api/prefs/schema` | GET | UI WIRED | Settings | — | Pref vocabulary |
| `/api/sections` | GET | UI WIRED | Settings, nav | — | Section order |
| `/api/sections` | PUT | UI WIRED | Settings | — | Reorder/hide |
| `/api/reminders` | GET | UI WIRED | Settings, Today | — | List reminders |
| `/api/reminders` | POST | UI WIRED | Settings | — | Add reminder |
| `/api/reminders/{rid}` | DELETE | UI WIRED | Settings | — | Delete reminder |

### Vault

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/vault/status` | GET | UI + TOOL | Vault | inspect_vault_status | Lock state |
| `/api/vault/unlock` | POST | UI WIRED | Vault (form) | — | Unlock |
| `/api/vault/lock` | POST | UI WIRED | Vault (button) | — | Lock |
| `/api/vault/names` | GET | UI WIRED | Vault (when unlocked) | — | Secret names |
| `/api/vault/set` | POST | UI WIRED | Vault (form) | — | Store secret |
| `/api/vault/{name}` | GET | DEFERRED | — | — | Read value (secure) |
| `/api/vault/{name}` | DELETE | UI WIRED | Vault (button) | — | Delete secret |

### Source Control

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/source-control/status` | GET | UI + TOOL | Projects | inspect_source_control | Repo status |
| `/api/source-control/history` | GET | UI + TOOL | Projects (disclosure) | inspect_source_control_history | Commit log |
| `/api/source-control/refresh` | POST | UI WIRED | Projects (step-up) | — | Refresh status |
| `/api/source-control/enrichment` | GET | UI WIRED | Projects (disclosure) | — | GitHub data |
| `/api/projects/status` | GET | UI WIRED | Projects, Today | — | Agent-sync estate |

### Chat / Reasoning

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/chat` | POST | UI WIRED | ChatScreen | — | Conversation |
| `/api/chat/providers` | GET | UI WIRED | ChatScreen (header) | — | Provider list |
| `/api/chat/test` | POST | UI WIRED | Settings (provider test) | — | Verify provider |

### Lab (homelab enrichment)

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/lab/state` | GET | UI WIRED | Lab (disclosure) | — | Operator packet |
| `/api/lab/settings` | GET | UI WIRED | Lab (disclosure) | — | Settings drift |
| `/api/lab/settings/inspect/{service}` | GET | API GAP | — | — | No detail UI yet |
| `/api/lab/settings/diff/{service}` | GET | API GAP | — | — | No detail UI yet |
| `/api/lab/health` | GET | UI WIRED | Lab (disclosure) | — | Service health |
| `/api/lab/deploy` | GET | UI WIRED | Lab (disclosure) | — | Deploy status |
| `/api/lab/secrets` | GET | UI WIRED | Lab (disclosure) | — | Secret audit |
| `/api/lab/resources` | GET | UI WIRED | Lab (disclosure) | — | VM resources |

### Native Lab (generic, portable)

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/native-lab/inventory` | GET | UI WIRED | Lab (main) | — | Service inventory |
| `/api/native-lab/health` | GET | UI WIRED | Lab (main) | — | Health monitoring |
| `/api/native-lab/settings` | GET | API GAP | — | — | No settings UI yet |
| `/api/native-lab/resources` | GET | UI WIRED | Lab (disclosure) | — | System resources |

### Native Discovery

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/discovery/status` | GET | UI WIRED | Interests (status) | — | Discovery status |
| `/api/discovery/sources` | GET | UI WIRED | Interests (list) | — | List sources |
| `/api/discovery/sources` | POST | UI WIRED | Interests (form) | — | Add source |
| `/api/discovery/interests` | GET | UI WIRED | Interests (list) | — | List interests |
| `/api/discovery/interests` | POST | UI WIRED | Interests (form) | — | Add interest |
| `/api/discovery/discover` | GET | UI WIRED | Interests (button) | — | Run discovery |

### Native Reconciler

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/reconciler/status` | GET | UI WIRED | Lab (disclosure) | — | Reconciler status |
| `/api/reconciler/diff/{service}` | GET | API GAP | — | — | No diff UI yet |
| `/api/reconciler/propose/{service}` | GET | API GAP | — | — | No proposal UI yet |

### Identity / Multi-user

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/identity/principal` | GET | UI WIRED | All screens (via usePrincipal) | — | Current user |
| `/api/identity/principal` | PUT | DEFERRED | — | — | Profile edit |
| `/api/identity/users` | GET | DEFERRED | — | — | Advanced admin |
| `/api/identity/users` | POST | DEFERRED | — | — | Advanced admin |
| `/api/identity/users/{user_id}` | DELETE | DEFERRED | — | — | Advanced admin |
| `/api/identity/agents` | GET | DEFERRED | — | — | Advanced admin |
| `/api/identity/agents` | POST | DEFERRED | — | — | Advanced admin |
| `/api/identity/agents/{agent_id}` | DELETE | DEFERRED | — | — | Advanced admin |

### Exports / Backup

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/exports/settings` | GET | UI WIRED | World (download) | — | Settings JSON |
| `/api/exports/world` | GET | UI WIRED | World (download) | — | World JSON |
| `/api/exports/story` | GET | UI WIRED | World (download) | — | Story JSON |
| `/api/backup` | GET | UI WIRED | World (download) | — | Full backup |

### World Writes

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/world/intent` | POST | UI WIRED | World (form) | — | Record intent |
| `/api/world/fact` | POST | UI WIRED | World (form) | — | Record fact |
| `/api/world/policy` | POST | UI WIRED | World (form) | — | Record policy |

### Apps

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/apps` | GET | DEFERRED | — | — | App registry |
| `/api/apps` | PUT | DEFERRED | — | — | App config |

### Themes

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/themes` | GET | DEFERRED | — | — | Theme packs |
| `/api/themes/{name}` | GET | DEFERRED | — | — | Theme detail |

### Ingress

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/ingress/rollups` | GET | DEFERRED | — | — | Traefik data |

### Tools

| Endpoint | Method | State | Screen | Brain Tool | Notes |
|----------|--------|-------|--------|------------|-------|
| `/api/tools` | GET | UI WIRED | — | — | Capability list for brain |

---

## Summary

| State | Count |
|-------|-------|
| UI WIRED | 35 |
| UI + TOOL | 11 |
| INTERNAL | 1 |
| API GAP | 5 |
| DEFERRED | 16 |
| **Total** | **68** |

---

## Providers — Default State

| Capability | Native Baseline | Default Provider | Status |
|------------|-----------------|------------------|--------|
| source_control | ✅ | native-git | Working |
| deployment | ❌ | none | not_configured |
| secrets | ❌ | none | not_configured |
| calendar | ❌ | none | not_configured |
| discovery | ❌ | native_discovery | Working |
| settings_validation | ✅ | native_reconciler | Working |
| service_validation | ❌ | native_lab | Working |
| update_discovery | ❌ | none | not_configured |
| memory | ❌ | none | not_configured |
| journal | ✅ | built-in | Working |
| reasoning | ❌ | ollama (qwen3:1.7b) | Working |
| notifications | ❌ | none | not_configured |
| scheduler | ❌ | none | not_configured |
| homelab_settings | ❌ | lab_cli (enrichment) | Optional |
| homelab_health | ❌ | lab_cli (enrichment) | Optional |
| homelab_deploy | ❌ | lab_cli (enrichment) | Optional |
| homelab_secrets | ❌ | lab_cli (enrichment) | Optional |
| homelab_resources | ❌ | lab_cli (enrichment) | Optional |

---

## What the Brain Can Discuss

The `/api/tools` endpoint returns capability status. The chat system prompt includes:

- world status, capabilities, health
- journal entries, history, search
- source control: repos, commits, branches
- projects: agent-sync state, work status
- lab: services, health, settings drift
- interests: discovery sources, recommendations
- vault: lock state (never secret values)
- reminders, preferences, sections

Read questions: answered from context.
Write requests: brain explains what would change, suggests the screen.

---

## Architecture Proved

```
DOMAIN / CAPABILITY
       │
   ┌───┴───┐
   │       │
  API   Tool adapter
   │       │
React UI  Worlds brain
```

- TodayScreen, LabScreen, ProjectsScreen, InterestsScreen, JournalScreen, VaultScreen, WorldScreen, SettingsScreen, ChatScreen — all consume real API data
- Brain receives capability context + tool descriptions from the same registry
- UI and brain share the same domain implementation
- No duplicate semantic implementations
