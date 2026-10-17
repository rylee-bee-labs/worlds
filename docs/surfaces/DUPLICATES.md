# DUPLICATE / COMPETING SYSTEMS — Worlds

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** known duplicate/competing systems · **Read this if:** two code paths look like they do the same job and you want to know which is live

**In short:** The known places where two surfaces do the same job. Reality only — no winner recommended except where a dated pass resolved one. Sibling: `ORPHANS.md`.

Only known duplicates. Reality only; no winner recommended.

**Note (2026-09-26):** the `api.py:NNN-NNN` line numbers and any `frontend/` paths
below were captured in the 2026-09-15/17 passes and may have drifted (the
`frontend/` tree is deleted; today's interface is `ui/`); find the named function
instead. The rows about auth, reminders, and tool approvals are **resolved**
(struck through, kept for provenance).

> **Update 2026-09-15 (D1–D3 auth/authority pass).** The two auth rows
> below were **resolved**: bearer, browser session (local/OIDC), and the
> loopback dev bypass now all resolve to one `Principal` in
> `require_auth`, and `require_step_up` consumes the persisted,
> principal-bound session grant. Both rows are retained, struck through,
> for provenance. See `AUTH-MATRIX.md`.

| Concern | Surface A | Surface B | Active callers A | Active callers B | Divergence |
|---|---|---|---|---|---|
| ~~Auth: bearer vs session identity~~ | ~~AUTH-001 require_auth (bearer → Principal)~~ | ~~AUTH-002/AUTH-003 session cookie + OIDC~~ | Every protected /api route | /api/auth/*, UI-011 | **RESOLVED 2026-09-15.** `require_auth` (api.py:211-276) resolves bearer → session cookie → fail closed; a session re-resolves against enabled identity records, so disabling a user revokes it. No parallel path remains. |
| ~~Step-up: IP/header vs session grant~~ | ~~AUTH-004 require_step_up~~ | ~~AUTH-008 session step_up_until grant~~ | All step-up-gated routes | /api/auth/step-up, UI-018 | **RESOLVED 2026-09-15.** `_step_up_authorized` (api.py:143-175) checks the live session grant first (`Session.has_step_up`, auth.py:31-42), then true-loopback, then `X-PW-StepUp`. Step-up is person-only. |
| Chat provider builders | CHAT-002 chat.py::build_chat_provider (Ollama + openai_compat) | CHAT-002 chat_registry.py::build_chat_provider (ollama, openai_compat, openai, anthropic, opencode) | None found for chat.py builder | app.py build_registry | chat.py copy is narrower and orphaned; registry copy is live. OllamaChat/OpenAICompatChat also duplicated as classes in both files. |
| Capability vocabularies | app.py::STANDARD_CAPABILITIES (18 caps) | provider_schemas.py::CAPABILITY_SCHEMAS (media, calendar, notifications, deployment, update_discovery, auth, reasoning) + inline capability descriptions in api.py::_capability_description | Registry/manifest + API-003 | Connections overview UI (API-020) | Three partial vocabularies: registry defines 18 (+ ingress/service_inventory/service_health/resource_monitoring added at runtime), schemas define a UI-facing 7, api.py carries a third descriptive dict. Overlaps but no single authority. |
| ~~Reminders read/write~~ | ~~API-067 via Scheduler singleton~~ | ~~TOOL-019 direct file read; TOOL-027 no-op~~ | API-067 + scheduler thread | chat tool loop | **RESOLVED (D1–D3).** TOOL-019 reads via a wired `Scheduler` (`tool_registry.py:1154-1168`); TOOL-027's executor persists through `Scheduler.add` (`:799-817`). No parallel read or no-op executor remains. |
| Update discovery | PROV-010 NativeUpdatesProvider (registry capability update_discovery, sources from connections "updates") | PROV-027 ComposeUpdateProvider + UpdateManager (CLI updates state machine, updates-session.json) | API-029 reads only UpdateManager, not the registry provider; manifest shows native-updates | CLI-018, API-029 | Two update systems with different stores (CFG-004 vs PW_UPDATES_PROJECT_DIR/compose) and different journals; /api/updates uses only the UpdateManager side. |
| Deployment | PROV-011 NativeDeploymentProvider (DockerComposeAdapter/SystemdAdapter, connections "deployment") | PROV-027 ComposeUpdateProvider (update flow) + PROV-021 LabDeploy (lab CLI) | status/observe only | CLI updates, lab API | Three deployment-shaped surfaces: native adapters (no live caller beyond observe), update apply path, and lab-side deploy status. |
| Secrets/SOPS | SECRET-001 Native Vault (vault.enc) | PROV-029 SopsBroker + PROV-030 SOPSVaultAdapter | Vault API/UI | none | SOPS paths exist as implemented code with no current caller; adapter write/delete unsupported. |
| Media construction | api.py::_build_media_engine (module-level in api.py) | tool_registry.py::_build_media_engine (env-based config dir) | API-053..057 | TOOL-020..023 | Two independent engine builders; API one reads config_dir captured at create_app, tool one re-derives from PW_CONFIG_DIR env at call time. Both bypass the Registry (media is never a registered capability provider). |
| Freshness vocabulary | agent_sync.py::freshness (observed_at ages) | lab_state.py freshness window (FRESHNESS timedelta) + observation-age.ts (frontend) | PROV-026 | PROV-021, UI | Per-surface freshness computation; concept shared ("dated observation, never timeless truth"), implementations differ per provider. |
| Preference/export vocabulary | A11Y-001 prefs.py PREFS (motion, contrast, text_scale, density, target_size, companion, accent) | docs/accessibility/PREFERENCES_SCHEMA.json (design schema includes motion choices beyond `reduced` that prefs.py does not accept) | API-030/031, CLI-012 | a11y contract + parity tests | Design schema is richer than implemented writable prefs; default agrees. Also exports vocabulary: settings-export whitelist vs world-export classification vs backup payload — three different "what is included" rules. |
| World/context reads (chat) | CHAT-009 build_world_context | chat_context._projects_block/_source_control_block re-derive project/git facts that also flow through PROV-026/PROV-001 | API-010 | API-010 | Context builder embeds its own projects/source-control snapshots alongside registry-based status; same data, two derivations inside one request. |
| Journal search paths | TOOL-004 search_journal (journal.search) | JOURNAL-008 NativeMemoryProvider.search (FTS5, API-016) | chat tool loop | API-016 | Two journal-search mechanisms: direct Journal.search vs derived FTS index. |
| Connections override merge | app.py::build_registry (merges connections.local.json) | API-080 source-control rollups read connections.json directly | all provider wiring | rollup endpoint | Private-override behavior is not uniform across read surfaces (recorded in ARCHITECTURE.md). |