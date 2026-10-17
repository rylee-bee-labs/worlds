# PROVIDER MATRIX — Worlds

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the capability → provider registration map · **Read this if:** you need to know how a capability gets its provider, and whether it is live

**In short:** Each capability, the provider that fills it, how that provider registers, and whether it is actually live. Registration = how the provider enters the live Registry.

Registration = how the provider enters the live Registry.

**Note (2026-09-26):** the `app.py:NNN` line numbers below are from the
2026-09-14/15 extraction and may have drifted — find the named provider instead.
Rooms (below) are **not** providers; see the note after the table.

| Capability ID | Provider ID | Registration | Active? | Reads | Writes | UI | API | CLI | Tool |
|---|---|---|---|---|---|---|---|---|---|
| CAP-001 source_control | PROV-001 NativeGit | auto (zero-provider baseline, app.py:181) | YES | git repos | none | UI-004, UI-012 | API-033/034/035/036 (enrichment separate) | CLI-013/014/015 | TOOL-005/006 |
| CAP-001 source_control | PROV-002 Gitea | connections type=gitea | PARTIAL (machinery; not default live) | forge API | none | — | — | — | — |
| CAP-001 source_control | PROV-003 FakeSourceControl | connections type=fake_source_control | NO (tests only) | none | none | — | — | — | — |
| — (source-control enrichment) | PROV-004 GitHubEnrichment | direct call in API-036 | YES | gh session | none | UI-004 | API-036 | — | — |
| CAP-002 deployment | PROV-011 NativeDeploymentProvider (+ DockerComposeAdapter/SystemdAdapter) | auto (app.py:438) | PARTIAL (status only; no live deploy caller) | CFG-005, compose, systemctl | none via provider | — | — | — | — |
| CAP-003 secrets | PROV-006 NativeVaultProvider | auto when vault present (app.py:389) | YES | STORE-003 | none (broker observes) | UI-007 | API-061..064 | — | TOOL-018 |
| CAP-003 secrets | PROV-029 SopsBroker / PROV-030 SOPSVaultAdapter | not registered | NO (orphan) | SOPS bundle | none (adapter write unsupported) | — | — | — | — |
| CAP-004 calendar | PROV-008 NativeCalendarProvider | auto (app.py:408) | YES | CFG-003 calendar, ICS | none | (no dedicated screen) | (no calendar API route) | — | — |
| CAP-005 discovery | PROV-013 NativeDiscovery | connections type=native_discovery + direct instantiation | YES | CFG-008, RSS/API | CFG-008 | UI-002 | API-049..052 | — | TOOL-014..017 |
| CAP-006 settings_validation | PROV-012 NativeLabSettings (native_lab slot) | connections type=native_lab | YES | native lab | none | UI-005 | API-047 | — | TOOL-011 |
| CAP-007 service_validation | PROV-012 NativeLabHealth | connections type=native_lab | YES | derived | none | UI-005 | API-046 | — | TOOL-009 |
| CAP-008 update_discovery | PROV-010 NativeUpdatesProvider | auto (app.py:428) | YES | CFG-004, release URLs | none | — | API-029 (via UpdateManager instead) | — | — |
| CAP-009 memory | PROV-007 NativeMemoryProvider | auto (app.py:399) | YES | STORE-002, STORE-012 | STORE-012 (derived) | (via chat) | API-016 | — | — |
| CAP-009 memory | PROV-005 LangGraphMemory | connections type=langgraph | PARTIAL (alternate) | external | none | — | API-016 (if active slot) | — | — |
| CAP-010 journal | (core-owned; Journal domain, not provider) | core | YES | STORE-002 | JOURNAL-001 | UI-006 | API-005..009 | CLI-003 | TOOL-003/004/024 |
| CAP-011 reasoning | CHAT-004..008 (Ollama/OpenAICompat/OpenAI/Anthropic/OpenCode) | connections reasoning entries (app.py:260) | YES | provider APIs | none | UI-008 | API-010..012 | — | TOOL-000 loop |
| CAP-012 notifications | PROV-009 NativeNotificationsProvider (WebhookAdapter/NtfyAdapter) | auto (app.py:418) | YES (observe) / send path uncalled | CFG-003 | HTTP POST on send | — | (no send route) | — | — |
| CAP-013 scheduler | (no provider registered) | capability defined only | PARTIAL | — | — | — | API-067 uses Scheduler directly (not via capability) | — | TOOL-019 |
| CAP-014 homelab_settings | PROV-016 LabSettings | lab_api connection | YES | lab CLI | none | UI-005 | API-038..040 | — | — |
| CAP-015 homelab_health | PROV-017 LabHealth / PROV-012 native | lab_api / native_lab | YES | lab CLI / system | none | UI-005 | API-041/046 | — | TOOL-009 |
| CAP-016 homelab_deploy | PROV-018 LabDeploy | lab_api connection | YES | lab CLI | none | UI-005 | API-042 | — | — |
| CAP-017 homelab_secrets | PROV-019 LabSecrets | lab_api connection | YES (names only) | lab CLI | none | UI-005 | API-043 | — | — |
| CAP-018 homelab_resources | PROV-020 LabResources / PROV-012 NativeLabResources | lab_api / native_lab | YES | lab CLI / system | none | UI-005 | API-044/048 | — | TOOL-010 |
| CAP-019 ingress | PROV-022 TraefikIngress | auto (app.py:201) | YES | Traefik API | none | UI-005 | API-078 | — | — |
| CAP-020 service_inventory | PROV-012 NativeLabInventory | native_lab / direct | YES | system | none | UI-005 | API-045 | — | TOOL-008 |
| CAP-021 service_health | PROV-012 NativeLabHealth | native_lab | YES | derived | none | UI-005 | API-046 | — | TOOL-009 |
| CAP-022 resource_monitoring | PROV-012 NativeLabResources | native_lab / direct | YES | system | none | UI-005 | API-048 | — | TOOL-010 |
| CAP-023 media | PROV-015 NativeMediaEngine (Plex/Sonarr/Radarr/Lidarr) | BYPASSES Registry — built in api.py::_build_media_engine and tool_registry | YES | provider APIs (tokens/api keys) | none | UI-003 | API-053..057 | — | TOOL-020..023 |
| CAP-024 auth | (schema only; OIDC config lookup) | provider_schemas | PARTIAL | STORE-017 | none | UI-021 | API-020 overview | — | — |
| — updates (CLI flow) | PROV-027 ComposeUpdateProvider / PROV-028 FakeUpdateProvider | CLI-018 build_provider | YES (compose native) | compose file, docker | compose image tags | — | API-029 (read-only view) | CLI-018 | — |
| — projects | PROV-026 AgentSyncProjectSensor | direct in API-079/TOOL-007 | YES | agent-sync stdout | none | UI-004 | API-079 | — | TOOL-007 |
| — lab state packet | PROV-021 LabState | direct in API-037 | YES | PW_LAB_CLI binary | none | UI-005 | API-037 | — | — |
| — ingress misc | PROV-023 HttpStatus, PROV-024 CandyDispenser | connections http_status / candy | YES (status probe) / demo | URL | none | — | — | — | — |
| — chat (CLI-less) | PROV-031 ChatProviderRegistry class | exists in chat_registry.py | NO (orphan) | — | — | — | — | — | — |

Duplicate/competing provider notes are in DUPLICATES.md.

## Not providers: rooms and the runtime registry (2026-09-26)

**Rooms are not capabilities or providers.** A room is any independent service
that serves the Play-Nice `room/0` contract (`GET /room`, `/room/cards`,
`/room/needs-you`, `/room/actions`, `POST /room/actions/{id}`). Worlds renders
them through `/api/rooms` (`API-088`); it never wraps a room as a Registry
provider. Newer sources that *are* providers/adapters but not in the table:

| Module | What it is |
|---|---|
| `providers/project_home.py` | Project Home source; token indirection `PW_PH_TOKEN_ENV` |
| `providers/content_db.py` | content provider behind the `list_content` / `search_content` tools |
| `providers/workbench.py` | Workbench provider, gated behind `PW_WORKBENCH` (off) |

**Runtime registry (Gap 1):** Worlds reads its **room list** from Project Home
`GET /api/rooms/registry` (`PW_ROOMS_REGISTRY_URL`, token env named by
`PW_ROOMS_REGISTRY_TOKEN_ENV`, cached 60 s, last-known-good persisted as
`rooms-registry.json`). `PW_ROOMS` is only a fallback. A room whose contract is
not in `SUPPORTED_CONTRACTS={room/0}` is reported `incompatible`. Registry row
fields: `id`, `name`, `base_url`, `public_url`, `contract`, `token_env`,
`insecure_tls`, `forward_principal`, `enabled`; `token_env` must match
`^PW_ROOM_[A-Z0-9_]+_TOKEN$`.

Live rooms (2026-09-26): **Workshop** (Project Home), **Studio**, **Engine room**
(homelab `lab room serve`), **Candy** (discovery). Room bearer tokens live in
Worlds' environment (names like `PW_ROOM_WORKSHOP_TOKEN`), values only in the
host's `.env` (mode 600). Source of truth: `src/personal_world/rooms.py`.