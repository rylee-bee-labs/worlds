# Project Worlds — Full System Inventory
# Every surface. Every connection. Current state.
# Generated from live codebase inspection.

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/CURRENT.md`) · **Read this if:** you need the 2026-09-13 inventory's endpoint/tool/provider tables. · **Superseded by:** `.project/CURRENT.md`.

**In short:** a 2026-09-13 "generated from live codebase" inventory claiming 663 tests, 19 read tools, 14 screens and 78 endpoints — the least current of the history set. Kept for provenance; treat no count as current. Since this record: the product is called Worlds, the interface is `ui/` with Bridge as home, and production runs on the transcode host.

---

## 1. COMPOSE SERVICES

| Service | Image | Status | Purpose |
|---------|-------|--------|---------|
| `core` | `ghcr.io/rylee-bee/personal-world:latest` | RUNNING | API server + frontend |
| `ollama` | `ollama/ollama:latest` | RUNNING | Local reasoning brain |
| `ollama-pull` | `ollama/ollama:latest` | ONE-SHOT | Downloads qwen3:1.7b on first boot |

**Volumes:**
- `world-data` — persistent world state (facts, intents, policies, journal, prefs, vault, sections, reminders)
- `ollama-data` — downloaded LLM models

**Environment:**
- `PW_API_TOKEN` (required) — API authentication
- `XIAOMI_MIMO_API_KEY` (optional) — Xiaomi MiMo reasoning provider

**Active connection (config/connections.json):**
```json
{
  "type": "ollama",
  "name": "worlds-local-brain",
  "capability": "reasoning",
  "base_url": "http://ollama:11434",
  "model": "qwen3:1.7b",
  "timeout": 120
}
```

---

## 2. CAPABILITIES (18 defined)

| Capability | Native Baseline | Default Provider | Status |
|------------|----------------|------------------|--------|
| `source_control` | ✅ | native-git | WORKING |
| `deployment` | ❌ | none | not_configured |
| `secrets` | ❌ | none | not_configured |
| `calendar` | ❌ | none | not_configured |
| `discovery` | ❌ | native_discovery | WORKING |
| `settings_validation` | ✅ | native_reconciler | WORKING |
| `service_validation` | ❌ | native_lab | WORKING |
| `update_discovery` | ❌ | none | not_configured |
| `memory` | ❌ | none | not_configured |
| `journal` | ✅ | built-in | WORKING |
| `reasoning` | ❌ | ollama (qwen3:1.7b) | WORKING |
| `notifications` | ❌ | none | not_configured |
| `scheduler` | ❌ | built-in (reminders) | WORKING |
| `homelab_settings` | ❌ | lab_cli (enrichment) | OPTIONAL |
| `homelab_health` | ❌ | lab_cli (enrichment) | OPTIONAL |
| `homelab_deploy` | ❌ | lab_cli (enrichment) | OPTIONAL |
| `homelab_secrets` | ❌ | lab_cli (enrichment) | OPTIONAL |
| `homelab_resources` | ❌ | lab_cli (enrichment) | OPTIONAL |

---

## 3. HTTP API ENDPOINTS (78 data operations)

### 3.1 Infrastructure

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/healthz` | GET | ✅ | Boot | — |
| `/api/setup/status` | GET | ✅ | Setup wizard | — |
| `/api/setup` | POST | ✅ | Setup wizard | — |

### 3.2 World Status

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/status` | GET | ✅ | Today, World, Settings | `inspect_world_status` |
| `/api/daily` | GET | ✅ | Today | — |
| `/api/daily` | POST | ✅ | Today (button) | — |
| `/api/actors` | GET | ✅ | World | — |
| `/api/manifest` | GET | ✅ | World | `inspect_manifest` |
| `/api/updates` | GET | ✅ | Settings | — |

### 3.3 Journal

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/journal` | GET | ✅ | Today, Journal | `read_journal` |
| `/api/journal` | POST | ✅ | Journal (form) | — |
| `/api/journal/supersede` | POST | ✅ | Journal (proposal) | — |
| `/api/journal/history` | GET | ✅ | Journal (disclosure) | — |
| `/api/journal/audit` | GET | ✅ | Journal (disclosure) | — |

### 3.4 Memory

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/memory/search` | GET | ✅ | Journal (search) | — |

### 3.5 Chat / Reasoning

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/chat` | POST | ✅ | Chat screen | BRAIN ENTRY |
| `/api/chat/providers` | GET | ✅ | Chat settings | — |
| `/api/chat/test` | POST | ✅ | Chat settings | — |

### 3.6 Tools

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/tools` | GET | ✅ | Tools display | TOOL REGISTRY |

### 3.7 Prefs / Sections / Reminders

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/prefs` | GET | ✅ | Settings | — |
| `/api/prefs` | PUT | ✅ | Settings | — |
| `/api/prefs/schema` | GET | ✅ | Settings | — |
| `/api/sections` | GET | ✅ | Nav, Settings | — |
| `/api/sections` | PUT | ✅ | Settings | — |
| `/api/reminders` | GET | ✅ | Settings, Today | `inspect_reminders` |
| `/api/reminders` | POST | ✅ | Settings | — |
| `/api/reminders/{rid}` | DELETE | ✅ | Settings | — |
| `/api/reminders/{rid}` | PATCH | ✅ | Settings | — |

### 3.8 Vault

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/vault/status` | GET | ✅ | Vault | `inspect_vault_status` |
| `/api/vault/unlock` | POST | ✅ | Vault (form) | — |
| `/api/vault/lock` | POST | ✅ | Vault (button) | — |
| `/api/vault/names` | GET | ✅ | Vault (list) | — |
| `/api/vault/set` | POST | ✅ | Vault (form) | — |
| `/api/vault/{name}` | GET | ✅ | Local only | — |
| `/api/vault/{name}` | DELETE | ✅ | Vault (button) | — |

### 3.9 Source Control

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/source-control/status` | GET | ✅ | Projects | `inspect_source_control` |
| `/api/source-control/history` | GET | ✅ | Projects | `inspect_source_control_history` |
| `/api/source-control/refresh` | POST | ✅ | Projects (step-up) | — |
| `/api/source-control/enrichment` | GET | ✅ | Projects (disclosure) | — |

### 3.10 Projects

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/projects/status` | GET | ✅ | Projects, Today | `inspect_projects` |

### 3.11 Lab (homelab enrichment)

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/lab/state` | GET | ✅ | Lab (disclosure) | — |
| `/api/lab/settings` | GET | ✅ | Lab (disclosure) | — |
| `/api/lab/settings/inspect/{service}` | GET | ✅ | — | — |
| `/api/lab/settings/diff/{service}` | GET | ✅ | — | — |
| `/api/lab/health` | GET | ✅ | Lab (disclosure) | — |
| `/api/lab/deploy` | GET | ✅ | Lab (disclosure) | — |
| `/api/lab/secrets` | GET | ✅ | Lab (disclosure) | — |
| `/api/lab/resources` | GET | ✅ | Lab (disclosure) | — |

### 3.12 Native Lab

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/native-lab/inventory` | GET | ✅ | Lab (main) | `inspect_lab_inventory` |
| `/api/native-lab/health` | GET | ✅ | Lab (main) | `inspect_lab_health` |
| `/api/native-lab/settings` | GET | ✅ | Lab (disclosure) | `inspect_lab_settings` |
| `/api/native-lab/resources` | GET | ✅ | Lab (disclosure) | `inspect_lab_resources` |

### 3.13 Discovery

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/discovery/status` | GET | ✅ | Interests | `inspect_discovery_status` |
| `/api/discovery/sources` | GET | ✅ | Interests | `list_discovery_sources` |
| `/api/discovery/sources` | POST | ✅ | Interests (form) | — |
| `/api/discovery/interests` | GET | ✅ | Interests | `list_interests` |
| `/api/discovery/interests` | POST | ✅ | Interests (form) | — |
| `/api/discovery/discover` | GET | ✅ | Interests (button) | `run_discovery` |

### 3.14 Reconciler

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/reconciler/status` | GET | ✅ | Lab (disclosure) | `inspect_reconciler_status` |
| `/api/reconciler/diff/{service}` | GET | ✅ | — | `inspect_reconciler_diff` |
| `/api/reconciler/propose/{service}` | GET | ✅ | — | — |

### 3.15 Exports / Backup

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/exports/settings` | GET | ✅ | World (download) | — |
| `/api/exports/world` | GET | ✅ | World (download) | — |
| `/api/exports/story` | GET | ✅ | World (download) | — |
| `/api/backup` | GET | ✅ | World (download) | — |

### 3.16 World Writes

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/world/intent` | POST | ✅ | World (form) | — |
| `/api/world/fact` | POST | ✅ | World (form) | — |
| `/api/world/policy` | POST | ✅ | World (form) | — |

### 3.17 Identity

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/identity/principal` | GET | ✅ | All screens | — |
| `/api/identity/principal` | PUT | ✅ | — | — |
| `/api/identity/users` | GET | ✅ | — | — |
| `/api/identity/users` | POST | ✅ | — | — |
| `/api/identity/users/{user_id}` | DELETE | ✅ | — | — |
| `/api/identity/agents` | GET | ✅ | — | — |
| `/api/identity/agents` | POST | ✅ | — | — |
| `/api/identity/agents/{agent_id}` | DELETE | ✅ | — | — |

### 3.18 Apps / Themes / Ingress

| Endpoint | Method | Domain ops? | UI? | Brain tool? |
|----------|--------|-------------|-----|-------------|
| `/api/apps` | GET | ✅ | — | — |
| `/api/apps` | PUT | ✅ | — | — |
| `/api/themes` | GET | ✅ | — | — |
| `/api/themes/{name}` | GET | ✅ | — | — |
| `/api/ingress/rollups` | GET | ✅ | — | — |

---

## 4. BRAIN TOOLS (19 read-only)

All tools call the same domain operations as the HTTP API.

| # | Tool ID | Capability | Args | Domain operation |
|---|---------|-----------|------|------------------|
| 1 | `inspect_world_status` | world | — | `world.summary()` |
| 2 | `inspect_manifest` | manifest | — | `registry.manifest()` |
| 3 | `read_journal` | journal | count | `journal.recent(count)` |
| 4 | `search_journal` | journal | query | `journal.search(query)` |
| 5 | `inspect_source_control` | source_control | — | `status_all()` |
| 6 | `inspect_source_control_history` | source_control | repo, limit | `history(repo, limit)` |
| 7 | `inspect_projects` | projects | — | `AgentSyncProjectSensor` |
| 8 | `inspect_lab_inventory` | lab | — | `NativeLabInventory.observe()` |
| 9 | `inspect_lab_health` | lab | — | `NativeLabHealth.observe()` |
| 10 | `inspect_lab_resources` | lab | — | `NativeLabResources.observe()` |
| 11 | `inspect_lab_settings` | lab | — | `NativeLabSettings.observe()` |
| 12 | `inspect_reconciler_status` | reconciler | — | `NativeSettingsReconciler.observe()` |
| 13 | `inspect_reconciler_diff` | reconciler | service | `reconciler.diff(service)` |
| 14 | `inspect_discovery_status` | discovery | — | `NativeDiscovery.observe()` |
| 15 | `list_discovery_sources` | discovery | — | reads sources |
| 16 | `list_interests` | discovery | — | reads interests |
| 17 | `run_discovery` | discovery | source | `discovery.discover(source)` |
| 18 | `inspect_vault_status` | vault | — | vault lock state |
| 19 | `inspect_reminders` | reminders | — | reads reminders.json |

**Write tools:** 0 (not exposed until approval framework is ready)

---

## 5. UI SCREENS (14 routed)

| # | Screen | Route | Hooks used | Real API? | Status |
|---|--------|-------|------------|-----------|--------|
| 1 | TodayScreen | `/` | 7 hooks | ✅ | WIRED |
| 2 | ChatRoute | `/chat` | delegates to ChatPanel | ✅ | WIRED |
| 3 | JournalScreen | `/journal` | 6 hooks + writes | ✅ | WIRED |
| 4 | VaultScreen | `/vault` | 2 hooks + CRUD | ✅ | WIRED |
| 5 | WorldScreen | `/world` | 4 hooks + exports/writes | ✅ | WIRED (companion hardcoded) |
| 6 | SettingsScreen | `/settings` | 10+ hooks + writes | ✅ | FULLY WIRED |
| 7 | ProjectsScreen | `/projects` | 4 hooks + lazy drill-down | ✅ | WIRED |
| 8 | LabScreen | `/lab` | 5 hooks | ✅ | WIRED |
| 9 | InterestsScreen | `/interests` | 5 hooks + writes | ✅ | WIRED |
| 10 | MediaScreen | `/media` | none | ❌ | STUB (empty state) |
| 11 | SetupWizard | `/setup` | setup API | ✅ | WIRED |
| 12 | LoginScreen | `/login` | prefs (auth check) | ✅ | WIRED |
| 13 | LabOperationsPanel | (sub-panel) | 4 hooks | ✅ | WIRED (lazy) |
| 14 | ChatScreen | (not routed) | chat API | ✅ | WIRED (legacy) |

---

## 6. PROVIDERS (29 implementations)

| # | Provider | Type | Capability | Registered? |
|---|----------|------|-----------|-------------|
| 1 | NativeGit | native | source_control | ✅ auto |
| 2 | HttpStatus | http_status | any | ✅ connections |
| 3 | Gitea | gitea | source_control | ✅ connections |
| 4 | FakeSourceControl | fake_source_control | source_control | ✅ connections |
| 5 | LangGraphMemory | langgraph | memory | ✅ connections |
| 6 | CandyDispenser | candy | discovery | ✅ connections |
| 7 | OllamaChat | ollama | reasoning | ✅ connections |
| 8 | OpenAICompatChat | openai_compat | reasoning | ✅ connections |
| 9 | OpenAIChat | openai | reasoning | ✅ connections |
| 10 | AnthropicChat | anthropic | reasoning | ✅ connections |
| 11 | OpenCodeChat | opencode | reasoning | ✅ connections |
| 12 | LabState | lab_api | homelab_health | ✅ connections |
| 13 | LabSettings | lab_api | homelab_settings | ✅ connections |
| 14 | LabHealth | lab_api | homelab_health | ✅ connections |
| 15 | LabDeploy | lab_api | homelab_deploy | ✅ connections |
| 16 | LabSecrets | lab_api | homelab_secrets | ✅ connections |
| 17 | LabResources | lab_api | homelab_resources | ✅ connections |
| 18 | NativeLabInventory | native_lab | service_inventory | ✅ connections |
| 19 | NativeLabHealth | native_lab | service_health | ✅ connections |
| 20 | NativeLabSettings | native_lab | settings_validation | ✅ connections |
| 21 | NativeLabResources | native_lab | resource_monitoring | ✅ connections |
| 22 | NativeDiscovery | native_discovery | discovery | ✅ connections |
| 23 | NativeSettingsReconciler | — | settings_validation | ✅ direct |
| 24 | GitHubEnrichment | — | source_control | direct (endpoint) |
| 25 | AgentSyncProjectSensor | — | projects | direct (endpoint) |
| 26 | TraefikIngress | — | ingress | ✅ auto |
| 27 | SopsBroker | — | secrets | standalone |
| 28 | SOPSVaultAdapter | — | vault | standalone |
| 29 | GenericServiceAdapter | — | reconciler | used by reconciler |

---

## 7. CHAT PROVIDERS (5 types)

| # | Provider | Type key | Tool-calling? |
|---|----------|----------|---------------|
| 1 | OllamaChat | `ollama` | ✅ `chat_with_tools` |
| 2 | OpenAICompatChat | `openai_compat` | ❌ |
| 3 | OpenAIChat | `openai` | ❌ |
| 4 | AnthropicChat | `anthropic` | ❌ |
| 5 | OpenCodeChat | `opencode` | ❌ |

---

## 8. WHAT'S WORKING END-TO-END

| Flow | Status |
|------|--------|
| Start compose → core + ollama boot | ✅ |
| Setup wizard → create token + vault | ✅ |
| Login → verify token → redirect | ✅ |
| Today → real status/daily/journal/reminders/repos/agents | ✅ |
| Lab → native inventory/health/resources + homelab enrichment | ✅ |
| Projects → source-control status/history/enrichment + agent-sync | ✅ |
| Interests → discovery sources/interests/discover + add forms | ✅ |
| Journal → entries + write + history + audit + memory search | ✅ |
| Vault → unlock/lock/set/delete CRUD | ✅ |
| World → manifest + exports + world writes (intent/fact/policy) | ✅ |
| Settings → prefs + sections + reminders + capabilities | ✅ |
| Chat → conversation with context awareness | ✅ |
| Brain → 19 callable tools via Ollama function-calling | ✅ |
| Chat tool loop → model selects tools → execute → explain | ✅ |

---

## 9. WHAT'S NOT WIRED

| Surface | Status | Reason |
|---------|--------|--------|
| MediaScreen | STUB | No media provider configured |
| CompanionPresence | STUB | Hardcoded mermaid (not reading companion pref) |
| WorldScreen companion section | HARDCODED | "The Mermaid" hardcoded |
| Identity endpoints | DEFERRED | No admin UI |
| Apps endpoints | DEFERRED | No apps UI |
| Themes endpoints | DEFERRED | No themes UI |
| Ingress endpoints | DEFERRED | No ingress UI |
| Write brain tools | DEFERRED | Approval framework not ready |
| OpenAI/Anthropic tool-calling | DEFERRED | Only Ollama has `chat_with_tools` |

---

## 10. TEST COVERAGE

- 663 Python tests passing
- Frontend: TypeScript compiles clean
- Token hex test: enforces no hardcoded colors
- Public safety tests: allow local ollama provider
- Dist safety test: verifies frontend build freshness
