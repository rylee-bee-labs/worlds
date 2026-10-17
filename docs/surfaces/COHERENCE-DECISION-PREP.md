# PROJECT WORLDS — COHERENCE DECISION PREP

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`../repo/WIRING-READINESS.md`](../repo/WIRING-READINESS.md)) · **Read this if:** you want the dated pre-wiring decision prep behind the D1–D12 calls · **Superseded by:** [`../repo/WIRING-READINESS.md`](../repo/WIRING-READINESS.md) and the code

**In short:** A dated, pre-wiring decision-preparation pass over three clusters (auth/identity, brain/tools, providers/storage) that produced the D1–D12 human decisions. It is retained for provenance, not as current guidance. Its vault findings (below: `encrypted: true` hardcoded, base64 fallback) were fixed by the 2026-09-15 finish pass — the vault now reports real Fernet state and fails closed with no fallback.

Read-only decision-prep pass over three clusters, built entirely on the
surface registry (`docs/surfaces/`). Baseline: branch
`docs/current-product-refresh`, SHA `2e728fd…61aa7`. Product is
"Project Worlds" (formerly Personal World). Registry IDs are stable; no
new surfaces are introduced. Where the registry left a question
unresolved, the specific implementation line was checked — those checks
are cited inline.

**What changed since:** the auth/identity findings above were superseded by the
2026-09-15 D1–D3 convergence (one `require_auth` seam; session + OIDC resolve to
one `Principal`); the interface is now `ui/`, and the product's core architecture
is **rooms** — neither is in this pass.

---

# 1. Auth + Identity

## 1.1 Current trust paths (exact, from code)

### Bearer path (the only gate that protects the API today)

```text
credential: PW_API_TOKEN env at boot — but AUTH-006 (_reconcile_boot_token)
            makes STORE-010 data/.env the winner at startup
→ validation: AUTH-001 require_auth (api.py::require_auth)
      no token configured → 503; no header → 401
→ principal: IDENT-003 resolve_principal
      single mode: hmac.compare_digest(token, instance_token) → Principal(id="primary", kind="person")
      multi mode: STORE-005 users.json/agents hashed-token match → person or agent Principal
→ API authorization: route dependencies + in-handler checks
      _is_admin (AUTH-007) on identity-admin routes
      _require_person (person-only: journal GET/POST, supersede, prefs, sections, display name)
→ step-up if required: AUTH-004 require_step_up = require_auth THEN
      _step_up_authorized(): loopback/::1/localhost/testclient OR any
      Python-classified private peer OR header X-PW-StepUp: 1
```

Nothing about a session ever enters this path. `request.state.principal`
is produced exclusively by bearer resolution.

### Session path

```text
login: UI-011 → POST /api/auth/login (auth_routes) → AUTH-002 login_local
      compares supplied token to PW_API_TOKEN (compare_digest)
→ session creation: SessionStore.create("owner", "local") — principal_id is
      the literal string "owner", NOT a resolved Principal
→ cookie: pw_session (httponly, secure, samesite=lax, 24h)
→ subsequent request: the cookie is sent, but…
→ what actually consumes it: NOTHING on the API surface.
      GET /api/auth/session and POST /api/auth/logout read the cookie.
      require_auth never reads pw_session; OIDC identity never maps to
      IDENT-001. A logged-in browser still needs pw_token (bearer) in
      localStorage for every protected call (UI-009 fetches prove it).
```

### OIDC path

```text
UI-011 → /api/auth/oidc/config (CFG-007 oidc.json) → /api/auth/oidc/login
→ external IdP → /api/auth/oidc/callback
→ state cookie compare → client_secret from env (SECRET-007)
→ token + userinfo fetched → auth.login_oidc(sub) → STORE-004 session
→ identity/principal: stops here. The OIDC sub becomes session
   principal_id; it never becomes an IDENT-001 Principal.
→ protected API: fails open-ish — the browser has a session but no
   pw_token bearer, so protected calls 401 → NAV-004 sends the person
   back to /login. Login "succeeds" and is then useless for the API.
```

### Step-up — the two halves and where they fail to converge

| | API step-up (AUTH-004) | Session step-up (AUTH-008) |
|---|---|---|
| Where | api.py::require_step_up + _step_up_authorized | auth.py::grant_step_up → sessions.json step_up_until |
| Trigger | dependency on every world/prefs/apps/sections/journal-supersede/identity/reminders/connections-write route | POST /api/auth/step-up (UI-018 conceptually) |
| What it checks | peer IP loopback-or-private, or `X-PW-StepUp: 1` | session has_step_up() within 300s |
| Consumed by | all require_step_up routes | nothing. The grant is written and never read by the gate. |
| Semantics | "extra write check", NOT fresh auth (matches ARCHITECTURE.md's own warning) | time-boxed grant, also not fresh auth |

Convergence point: none. AUTH-004 consults `require_auth` (bearer) and
the request's IP/headers. AUTH-008 lives in STORE-004. They never read
each other's state.

## 1.2 Principal model (answered literally)

- **Canonical Principal:** `identity.py::Principal` (IDENT-001) —
  frozen dataclass: id, kind (person/agent/service), owner_id,
  display_name, scopes, auth_level, source. auth_level is always 1 in
  current code (2/3 defined but never granted).
- **Who creates it:** only `IDENT-003 resolve_principal`, called only
  by AUTH-001 per request. Not persisted anywhere.
- **Authentication paths that can create it:** bearer only. OIDC and
  session logins cannot produce a Principal.
- **Person vs agent:** in multi mode, `IdentityStore.match_token`
  returns users or agents records; agents get kind="agent" with
  owner_id and scopes. In single mode, only the "primary" person
  exists.
- **Where scopes matter today:** exactly one enforcement point —
  `_is_admin` (api.py:1697: `"admin" in principal.scopes`). The
  declared agent vocabulary {read, write, journal, apps} (IDENT-006)
  is validated at agent creation but never consulted on any route; the
  only agent restriction actually enforced is `_require_person`
  (blanket person-only refusal). A scope-less agent has exactly the
  same API reach as the primary person except person-only surfaces.
- **Multi-user mode changes:** `PW_IDENTITY_MODE=multi` switches
  principal resolution to STORE-005 hashed tokens, bootstraps
  `legacy_primary` (identity.py:202) so the instance token stays the
  primary person's credential, and routes world/journal/prefs/sections
  through IDENT-007 `_user_paths` per-person trees (STORE-021).
- **Global data even in multi mode:** STORE-003 vault.enc (one
  passphrase, one instance), STORE-007 apps.json, STORE-006
  reminders.json, STORE-008 updates-session, STORE-004 sessions,
  connections (STORE-014/015), STORE-018 discovery.json, STORE-019
  reconciler desired, STORE-012 FTS index (built only from the shared
  journal), all provider wiring, and the chat/tool loop (which always
  uses the shared `journal` and world_path globals — `_state_for` is
  only consulted on some journal/prefs/sections routes).

## 1.3 Auth duplication table

| Concern | Surface IDs | What A does | What B does | Shared state? | Divergence |
|---|---|---|---|---|---|
| Bearer vs session | AUTH-001 vs AUTH-002 | Validates instance/user token per request; resolves Principal; 503/401 fail-closed | Creates/validates server-side sessions with 24h sliding expiry | None | Two independent credential systems; a valid session grants zero API rights |
| Bearer vs OIDC-produced session | AUTH-001 vs AUTH-003 | Token → Principal (single/multi) | IdP-verifies identity → session with auth_method="oidc" | None | OIDC proves identity strongly, then the proof is discarded at the API boundary |
| API step-up vs session step-up | AUTH-004 vs AUTH-008 | IP/header check per request, on bearer | 300s time-boxed grant persisted in STORE-004 | None (sessions.json written by B, never read by A) | Two unrelated definitions of "step-up"; B's grant cannot satisfy A's gate |
| Primary/admin vs scopes | AUTH-007 vs IDENT-006 | `id == "primary"` OR "admin" in scopes = admin | read/write/journal/apps declared for agents, never enforced | STORE-005 (scopes stored on agent records) | Scope model is declarative only; kind-based `_require_person` is the only other identity rule |
| Global vs per-user state | IDENT-007 `_user_paths` vs everything else | Routes journal/prefs/sections/notes to per-person trees in multi | vault/apps/reminders/identity/sessions/providers remain instance-global | Only STORE-001/002 (+ layout/prefs inside them) are per-user | "Whose state is this?" answered for 3 stores, global for ~9 others |
| Single vs multi bootstrap | AUTH-006 boot-token reconciliation vs `legacy_primary` | data/.env token wins at boot in both modes | Multi boot attaches instance token to "primary" user record | Both feed AUTH-001 | Coherent — the two mechanisms agree; instance token never locks the owner out |

## 1.4 Candidate invariants (auth)

> **AUTH-I1: Every authenticated API request resolves to exactly one
> Principal before handler code runs.**
> Supporting: AUTH-001, IDENT-001/003 (already true on bearer path).
> Contradicting: AUTH-002/003 (sessions bypass principal resolution),
> `/api/chat/test`-style routes that historically ran unauthenticated
> (now gated — API-012).
> Blast radius if adopted: Medium — require_auth gains a session branch;
> auth_routes unchanged.

> **AUTH-I2: Two independent credential systems must not both be
> reachable for the same action without a documented precedence.**
> Supporting: AUTH-001 vs AUTH-002/003 divergence table; boot-token
> reconciliation (AUTH-006) already embodies "documented precedence"
> for tokens (STORE-010 wins).
> Contradicting: sessions vs bearer currently coexist with no
> precedence statement.
> Blast radius: Large (touches every protected route).

> **AUTH-I3: Step-up for a destructive action is a property of the
> credential event, not the network location.**
> Supporting: AUTH-008 (time-boxed grant), AUTH-004's header path is a
> nod in this direction; ARCHITECTURE.md names "not verified fresh
> authentication" as a current restriction, and the finish line
> requires step-up for severe changes.
> Contradicting: AUTH-005 (loopback and private peers pass with no
> credential event).
> Blast radius: Medium — Docker bridge deployments rely on private-peer
> pass-through; changing it can lock owners out.

> **AUTH-I4: Identity rules (person-only, admin-only) are evaluated at
> one seam, not sprinkled per handler.**
> Supporting: `_is_admin`/`_require_person` exist as helpers but each
> route re-invokes them ad hoc (17 enforcement points across api.py).
> Blast radius: Medium.

> **AUTH-I5: Agent scope declarations must be enforced or not issued.**
> Supporting: IDENT-006 declares read/write/journal/apps; only "admin"
> is ever checked. Agents today can read/act far beyond "read".
> Contradicting: no scope enforcement anywhere else.
> Blast radius: Medium (agent tokens currently near-equal to persons).

---

# 2. Brain + Tools

## 2.1 Tool classification (code-verified; 29 tools, TOOL-000 container)

| Tool | ID | Class | Note |
|---|---|---|---|
| inspect_world_status | TOOL-001 | PURE READ | |
| inspect_manifest | TOOL-002 | PURE READ | |
| read_journal | TOOL-003 | PURE READ | |
| search_journal | TOOL-004 | PARTIAL | calls `journal.search`, which does not exist on Journal (hasattr guard → empty result) |
| inspect_source_control | TOOL-005 | PURE READ | |
| inspect_source_control_history | TOOL-006 | PURE READ | |
| inspect_projects | TOOL-007 | PURE READ | subprocess per call |
| inspect_lab_inventory | TOOL-008 | PURE READ | fresh NativeLabInventory per call |
| inspect_lab_health | TOOL-009 | PURE READ | rebuilds inventory internally |
| inspect_lab_resources | TOOL-010 | PURE READ | |
| inspect_lab_settings | TOOL-011 | PURE READ | |
| inspect_reconciler_status | TOOL-012 | PURE READ | |
| inspect_reconciler_diff | TOOL-013 | PARTIAL | desired-only; admits observed state unavailable |
| inspect_discovery_status | TOOL-014 | PURE READ | |
| list_discovery_sources | TOOL-015 | PURE READ | |
| list_interests | TOOL-016 | PURE READ | |
| run_discovery | TOOL-017 | READ WITH SIDE EFFECT | fetches external content, can persist to CFG-008 despite read_write="read" |
| inspect_vault_status | TOOL-018 | PURE READ | lock state only; hardcodes `encrypted: true` even when base64 fallback active |
| inspect_reminders | TOOL-019 | READ WITH SIDE EFFECT? (no) | direct file read; no side effect but a duplicate path |
| inspect_media_status | TOOL-020 | PURE READ | builds own engine |
| inspect_media_recent | TOOL-021 | PURE READ | |
| inspect_media_activity | TOOL-022 | PURE READ | |
| search_media | TOOL-023 | PURE READ | |
| propose_journal_entry | TOOL-024 | PROPOSAL | in-memory store |
| propose_world_intent | TOOL-025 | PROPOSAL | |
| propose_world_fact | TOOL-026 | PROPOSAL | |
| propose_reminder | TOOL-027 | PROPOSAL → STUB executor | |
| propose_reconciler_apply | TOOL-028 | PROPOSAL → STUB executor | |
| execute_approved_write | TOOL-029 | EXECUTOR (PARTIAL semantics) | approval is an argument |

## 2.2 Mutation chains — where each succeeds or breaks

Common head for all: model call inside API-010 → `_chat_with_tools_loop`
(max 3 rounds) → `tool_reg.invoke`. Note: **no human is in this loop** —
the "approval" is whatever the model passes to TOOL-029 in the next
round. The human sees the final text; proposals live in process memory.

**TOOL-024 journal write**
```text
model → propose_journal_entry → _proposals["proposal-N"] (pending)
→ (same model, same loop) execute_approved_write(proposal_id, approved=True)
→ journal.record("observation", text, source="brain-tool")   ← succeeds
→ persistence: journal.ndjson append                           ← succeeds
→ provenance: source=brain-tool, no proposal id in journal
→ visible result: "executed" to the model; human sees only chat text
```
Break: approval step is model-supplied, not human; proposal store
vanishes on restart (pending proposals unrecoverable).

**TOOL-025 world intent**
```text
→ world.set_intent(proposal["key"], proposal["intent"])  ← succeeds
→ persistence: save_world is NOT called in the executor — mutation lives
  only in the per-request World instance (LIFE-009 loads fresh world per
  request; the chat request's World is discarded after the response)
→ so the "executed" result reports a mutation that does not survive the
  request
```
**Breaks at persistence.**

**TOOL-026 world fact** — identical shape to TOOL-025: mutates
in-memory World; no `save_world`; breaks at persistence.

**TOOL-027 reminder**
```text
→ propose_reminder → pending proposal
→ execute_approved_write: ptype=="reminder" → proposal["status"]="executed"
→ NOTHING touches STORE-006; no Scheduler call
```
**Breaks at executor: reports executed, performs no mutation.**

**TOOL-028 reconciler apply**
```text
→ propose_reconciler_apply reads PROV-014 desired state (private attr access)
→ executor: proposal["status"]="executed" + note "Actual provider apply
   requires adapter."
```
**Breaks at execution — by design note, but reports success.**

**TOOL-029 itself** — executes any pending proposal id in memory. A
proposal can be executed by the model in the very next tool round with
`approved=true` (a model-generated boolean). `requires_step_up=True` on
the tool metadata is not enforced anywhere in the tool path (step-up is
an HTTP dependency concept; the tool loop never sees the request).

## 2.3 Approval semantics (literal answers)

- **Where does approval live?** In `_proposals` dict,
  tool_registry.py:505 — process memory.
- **Is approval server-verified?** No. `_execute_approved_write` trusts
  the `approved` boolean argument, which in the only real call path is
  produced by the model.
- **Is approval persisted?** No — only the proposal's status string in
  memory ("pending/executing/executed/rejected").
- **Can approval survive restart?** No. Process restart loses both
  proposals and any approval state.
- **Can an executor be invoked without a durable approval record?**
  Yes — that is the normal path.
- **Which component supplies the approved flag?** The model, via tool
  arguments parsed in `_chat_with_tools_loop`.
- **Provenance for proposal creation?** None persisted (proposal id is
  a counter).
- **Provenance for approval?** None.
- **Provenance for execution?** Partial: TOOL-024 journal write carries
  `source="brain-tool"`; world intent/fact writes carry the
  proposal's original provenance only if any — none is attached;
  `MutationDenied`/policy gates are bypassed because
  `world.record_fact/set_intent` are the raw mutators (they do not
  consult policies — only `set_policy`/`promote_lore`/pack install do).

## 2.4 Read-path inconsistencies (tool vs API/UI)

| Concern | API/UI path | Tool path | Divergence |
|---|---|---|---|
| Journal read | API-005 `current_events` (calm view, superseded hidden) | TOOL-003 `journal.recent` (raw, includes superseded) | Model may read entries the UI hides as corrected |
| Journal search | JOURNAL-008 FTS5 via API-016 | TOOL-004 `journal.search` → **missing method** → empty results | Tool silently returns `entries: []` |
| Memory search | PROV-007 provider through registry | (not tool-exposed) | Tool registry has no memory tool; N/A |
| Reminder read | API-067 Scheduler instance (in-memory, one per app) | TOOL-019 direct `reminders.json` read via PW_DATA_DIR env | Env may disagree with create_app's data_dir; no Scheduler state (loaded flag) |
| Media engine | api.py `_build_media_engine` reads create_app's `config_dir/connections.json` | tool_registry `_build_media_engine` re-derives PW_CONFIG_DIR env at call time | Env vs constructor paths can disagree in tests/embedded runs |
| Reconciler inspection | API-058/059 through PROV-014 observe/diff | TOOL-013 reads `reconciler._desired` private attribute | Tool bypasses the public diff API |
| World status | API-003 registry.status_map + actors | TOOL-001 world.summary() only (no capability statuses) | Tool sees less than the API |
| Chat context | CHAT-009 build_world_context (journal, registry, projects, git) | Same builder for tools loop | Consistent |

## 2.5 Candidate invariants (brain)

> **TOOL-I1: A successful mutating tool result must correspond to an
> observable authoritative state change.**
> Supporting: TOOL-024 (true), JOURNAL-001.
> Contradicting: TOOL-025/026 (no save_world), TOOL-027/028 (no mutation
> at all).
> Blast radius: Medium — one executor path.

> **TOOL-I2: Human approval must not be represented solely by
> model-generated arguments.**
> Supporting: the Journal screen supersede flow (API-007 + UI-006) and
> the source-control refresh flow (API-035) — both gate the act behind
> step-up and label the human as approver in journal provenance.
> Contradicting: TOOL-029's `approved` parameter.
> Blast radius: Medium-Large (tool loop design).

> **TOOL-I3: Approval evidence must be persisted and auditable.**
> Supporting: JournalKind.APPROVAL exists (model.py) and is used by
> JOURNAL-003 supersede and updates apply (updates.py:265).
> Contradicting: `_proposals` (no journal event for proposal, approval,
> or execution).
> Blast radius: Small-Medium.

> **TOOL-I4: Write tools must be distinguishable from read tools by the
> schema the model sees.**
> Supporting: read_write field exists in Tool metadata.
> Contradicting: TOOL-017 (run_discovery, read-labeled, performs
> fetch+persist).
> Blast radius: Small.

> **TOOL-I5: Domain gates (MutationDenied, person-only) apply to tool
> executors the same as API writes.**
> Supporting: API-075..077 route world writes through step-up; API-006
> enforces person-only.
> Contradicting: TOOL-029 path bypasses require_step_up (HTTP concept)
> and writes with source="brain-tool" regardless of principal kind.
> Blast radius: Medium.

> **TOOL-I6: Tool read paths must equal API read paths for the same
> question.**
> Supporting: TOOL-005/006 share source_control functions with API-033/034.
> Contradicting: TOOL-003/004 (recent vs current_events; search missing),
> TOOL-019 (direct file), TOOL-013 (private attr).
> Blast radius: Small (per-tool).

---

# 3. Providers + Storage

## 3.1 Capability ownership matrix

| Capability | ID | Primary implementation | Alternate(s) | Registry-owned? | Direct/bypass consumers | Persistent state |
|---|---|---|---|---|---|---|
| source_control | CAP-001 | PROV-001 NativeGit (registry slot) | PROV-002 Gitea; PROV-003 Fake | YES | API-033/034 (direct functions, same module), CLI-013..015, TOOL-005/006; enrichment PROV-004 direct | external repos |
| source-control enrichment | — | PROV-004 GitHubEnrichment | PROV-002 | BYPASS (direct call in API-036) | UI-004 | external gh session |
| deployment | CAP-002 | PROV-011 NativeDeploymentProvider | PROV-027 ComposeUpdateProvider (apply); PROV-021 LabDeploy (status) | registry YES (native) | no live caller beyond observe; CLI updates separate | CFG-005 config |
| secrets | CAP-003 | SECRET-001 Native Vault via PROV-006 | PROV-029/030 SOPS (orphans) | registry YES | API-061..064 direct `_vault` object (not via registry), UI-007, TOOL-018 | STORE-003 |
| calendar | CAP-004 | PROV-008 NativeCalendarProvider | — | registry YES | none (no route/tool) | CFG-003 |
| discovery | CAP-005 | PROV-013 NativeDiscovery | — | registry YES (when configured) + direct instantiation in API/TOOLS | API-049..052, TOOL-014..017 | STORE-018 (outside data dir) |
| settings_validation | CAP-006 | PROV-012 NativeLabSettings slot | LabSettings (lab CLI) | registry YES | API-047, TOOL-011 | native |
| service_validation | CAP-007 | PROV-012 NativeLabHealth | LabHealth | registry YES | API-046, TOOL-009 | derived |
| update_discovery | CAP-008 | PROV-010 NativeUpdatesProvider | PROV-027 + UpdateManager (CLI flow) | registry YES, but API-029/CLI-018 use UpdateManager only | API-029, CLI-018 | STORE-008, CFG-004 |
| memory | CAP-009 | PROV-007 NativeMemoryProvider | PROV-005 LangGraphMemory | registry YES | API-016 (provider_for), TOOL-004 (does NOT use it) | STORE-012 derived |
| journal | CAP-010 | core Journal (not provider) | — | core-owned | everything | STORE-002 |
| reasoning | CAP-011 | CHAT-004..008 via registry | CHAT-002 chat.py builder (orphan); PROV-031 ChatProviderRegistry (orphan) | registry YES | API-010..012 | none (ephemeral) |
| notifications | CAP-012 | PROV-009 NativeNotificationsProvider | — | registry YES | observe only; no send caller | CFG-003 |
| scheduler | CAP-013 | **no provider** — LIFE-004 Scheduler used directly | — | registry: capability defined, empty | API-067, LIFE-003/004 | STORE-006 |
| homelab_settings/health/deploy/secrets/resources | CAP-014..018 | Lab* via lab_api connection | PROV-012 native-lab | registry YES (5 slots per lab_api conn) | API-038..044, UI-005 | external lab |
| ingress | CAP-019 | PROV-022 TraefikIngress | — | registry YES | API-078 | external |
| service_inventory | CAP-020 | PROV-012 NativeLabInventory | — | registry YES | API-045, TOOL-008 | system |
| service_health | CAP-021 | PROV-012 NativeLabHealth | — | registry YES | API-046 | derived |
| resource_monitoring | CAP-022 | PROV-012 NativeLabResources | — | registry YES | API-048, TOOL-010 | system |
| media | CAP-023 | PROV-015 NativeMediaEngine | — | **BYPASS** (never registered; CAPABILITY_SCHEMAS declares it) | API-053..057, TOOL-020..023 | provider APIs only |
| auth (schema) | CAP-024 | provider_schemas entry only | — | N/A | API-020 overview | STORE-017 |
| projects | — | PROV-026 AgentSyncProjectSensor | PROV-001 | BYPASS (direct) | API-079, TOOL-007 | external binary |

## 3.2 Duplicate provider paths (traced)

**Chat — `chat.py` vs `chat_registry.py`**
- Callers: app.py imports `build_chat_provider` from chat_registry
  (verified). No caller of chat.py's builder exists.
- Reads/writes: both read the same connections dict; write nothing.
- State: none. Behavior: registry copy supports 5 provider types; chat.py
  copy supports 2; chat.py additionally has `chat_once`, `build_chat_messages`,
  `extract_proposal` (live, used by API-010) — so the *module* is live,
  its *builder and Ollama/OpenAICompat classes* are dead duplicates.
- Completely unused: chat.py `build_chat_provider`, `OllamaChat`,
  `OpenAICompatChat` (chat.py versions). chat_registry's
  `ChatProviderRegistry` class: unused.

**Updates — NativeUpdatesProvider vs UpdateManager/ComposeUpdateProvider**
- Callers: PROV-010 registered in the registry (manifest-visible);
  API-029 and CLI-018 construct `UpdateManager(build_provider(...))`
  directly and never consult the registry provider.
- State: PROV-010 reads CFG-004 (connections "updates" key);
  UpdateManager reads `$PW_UPDATES_PROJECT_DIR` compose project and
  writes STORE-008 + journal APPROVAL/RECONCILIATION events.
- Behavior: PROV-010 is check-only release watching; UpdateManager is a
  full check/preview/apply/rollback state machine. No overlap in state.

**Deployment — NativeDeploymentProvider vs update apply vs LabDeploy**
- PROV-011 (DockerComposeAdapter `status/deploy`, SystemdAdapter):
  registered; only `observe()` is consumed via status_map. `deploy()`
  has no caller.
- PROV-027 (ComposeUpdateProvider): invoked by UpdateManager apply
  (`docker compose` rewrite + verify) — CLI-018 only.
- PROV-021 LabDeploy: lab-CLI packet status via API-042.
- State differs: compose project dir vs CFG-005 connections "deployment"
  vs external lab. Behavior: three honest status views, one real
  mutation path (update apply), one dead mutation path
  (DockerComposeAdapter.deploy).

**Media — API builder vs tool builder vs main Registry**
- api.py `_build_media_engine`: reads create_app `config_dir` +
  connections.json; used by API-053..057.
- tool_registry `_build_media_engine`: re-derives `PW_CONFIG_DIR` env;
  used by TOOL-020..023.
- Main Registry: media never registered (CAPABILITY_SCHEMAS has the
  vocabulary; `connections_overview` special-cases it via
  `config.get("media", …)` keys that `_read_all` would surface only if
  the config nests them — live deployments keep media entries in the
  `connections` array, so overview's "configured" detection for media
  reads a key that neither STORE-014 nor 015 typically contains).
- State: none persistent. Behavior: same engine class, two construction
  sites; API side honors the app's config_dir, tool side trusts env.

**Secrets — Native Vault vs SOPS scaffolds**
- Vault (vault.py): live singleton in create_app; API-061..064 use the
  `_vault` object directly (not through the Registry's secrets slot);
  PROV-006 wraps it for the registry/manifest.
- SopsBroker (adapters.py:229): zero callers. SOPSVaultAdapter
  (vault.py:230): zero callers; write/delete unsupported by design.
- State: vault.enc vs external SOPS bundle — entirely different stores.

**Scheduler — capability vs direct usage**
- CAP-013 defined with no provider; API-067 and LIFE-004 use the
  Scheduler class directly. TOOL-019 bypasses even that (file read).
- State: STORE-006 shared by all three readers; only Scheduler + API
  write.

## 3.3 Storage ownership (authoritative stores)

| Store | Domain owner | Readers | Writers | User scope | Export | Backup | Restore path | Secret? | Rebuildable? |
|---|---|---|---|---|---|---|---|---|---|
| STORE-001 world.json | DOMAIN-001 World | all (per-request load) | save_world, setup, CLI init/cement, tool executors (broken), API-030/032/075..077 | per-user in multi (STORE-021) | settings/world exports (filtered) | YES via backup_payload | init + manual re-entry | no | partially |
| STORE-002 journal.ndjson | JOURNAL-001/002 | everything | every surface (append-only) | per-user in multi | story export | YES | none (primary) | contains personal data | no |
| STORE-003 vault.enc | SECRET-001 Vault | vault API, PROV-006 | vault set/delete; setup init | GLOBAL (instance) | never (correct) | **NO** | passphrase + re-entry | YES | no |
| STORE-005 users.json | IDENT-002 | AUTH-001 multi, admin routes | identity admin API, profile PUT | GLOBAL records; hashed tokens per person | no | **NO** | none (tokens lost = re-provision) | hashed tokens (yes-ish) | no |
| STORE-006 reminders.json | LIFE-004 Scheduler | API-067, TOOL-019 | Scheduler, API-067 | GLOBAL | no | **NO** | re-create by hand | no | yes |
| STORE-007 apps.json | API-066 | apps API, UI | PUT /api/apps | GLOBAL | no | **NO** | re-create | no | yes |
| STORE-014 connections.json | CONN-002 / LIFE-002 | build_registry, API-019/080 | manual only | GLOBAL | settings-export shape only (capabilities/providers) | NO | re-derive from example | env names only (no values) | yes |
| STORE-015 connections.local.json | CONN-002 | build_registry merge | API-021/022 writes | GLOBAL | no | **NO** | none — API-created connections are LOST on wipe | may hold env-referenced URLs (private) | no |
| STORE-018 discovery.json | PROV-013 | API-049..052, TOOL-014..017 | API-050/051 POSTs, discover feedback | GLOBAL (home dir, outside PW_DATA_DIR) | no | **NO** | re-add by hand | no | partially (user data) |
| STORE-019 reconciler/desired | PROV-014 | API-058..060, TOOL-012/013/028 | manual only | GLOBAL (home dir) | no | **NO** | re-author | no | yes (user-authored) |
| STORE-021 per-user dirs | IDENT-007 User | _user_paths (multi) | same as 001/002 per person | per-user | world/journal exports per user (global only via CLI default) | only the global pair | manual | no | partially |

Also note: STORE-004 sessions, STORE-008 updates-session, STORE-009
setup marker, STORE-010 data/.env, STORE-012 FTS, STORE-016 prompts,
STORE-017 oidc.json — outside backup; first three are ephemeral,
prompts/oidc re-derivable, data/.env is the setup credential (not
backed up, not re-derivable).

## 3.4 Personal data boundary

| Data | Store | Personal? | Secret? | Global/per-user | Exported? | Backed up? | Recoverable today? |
|---|---|---|---|---|---|---|---|
| Facts/intents/policies/lore | STORE-001 | yes (world-class) | no | per-user (multi) / global (single) | world-export (secrets/private lore excluded) | YES | manual from backup |
| Journal events | STORE-002 | yes | no | per-user (multi) | story-export (disclosure-filtered) | YES | no (primary evidence) |
| Vault values | STORE-003 | yes | YES | global | never | NO | passphrase only |
| Identity tokens | STORE-005 | yes | hashed | global records | no | NO | re-provision |
| Reminders | STORE-006 | mildly | no | global | no | NO | re-create |
| Apps launcher | STORE-007 | mildly | no | global | no | NO | re-create |
| Connections (UI-created) | STORE-015 | config | env refs | global | no | NO | **lost** |
| Discovery sources/interests/feedback | STORE-018 | yes (interests) | no | global | no | NO | re-enter |
| Reconciler desired state | STORE-019 | mildly | no | global | no | NO | re-author |
| Sessions | STORE-004 | no | session ids | global | no | NO | re-login |
| Update session | STORE-008 | no | no | global | no | NO | harmless |
| Setup token | STORE-010 | yes | YES | global | no | NO | re-run setup (409 — marker blocks; deleting marker re-arms) |
| FTS index | STORE-012 | derived | no | global (shared journal only) | no | NO | YES reindex |
| Theme packs | STORE-013 | taste | no | global | no | NO | re-place files |

If the runtime disappeared: journal + world survive only via
backup_payload (which excludes everything in rows marked NO).

## 3.5 Candidate invariants (providers/storage)

> **PROV-I1: A capability should have one authoritative runtime owner.**
> Supporting: CAP-011 (reasoning — registry slot), CAP-001 (NativeGit).
> Contradicting: CAP-008 (two update systems), CAP-002 (three deployment
> surfaces), CAP-023 (media bypass), CAP-013 (scheduler empty).
> Blast radius: Large per affected capability.

> **PROV-I2: If the Registry is the wiring truth, API routes must
> resolve providers through it.**
> Supporting: API-016 (memory via provider_for), API-010 (reasoning).
> Contradicting: API-053..057 + TOOL-020..023 (media builds engines
> directly), vault routes use the singleton, PROV-026 direct.
> Blast radius: Medium.

> **PROV-I3: Native baselines must degrade honestly when a configured
> provider is removed.**
> Supporting: app.py source_control baseline logic (enrichment slot
> degrades back to NativeGit), FakeSourceControl substitution tests.
> Contradicting: media (no registry slot to degrade into), scheduler
> (no provider at all).
> Blast radius: Small.

> **STORE-I1: User-authored durable state must have a documented
> recovery path.**
> Supporting: STORE-001/002 via backup_payload; CLI-008 contract.
> Contradicting: STORE-015 (API-created connections), STORE-018
> (discovery), STORE-019 (desired state), STORE-005, STORE-006,
> STORE-007, STORE-010, STORE-013 — no backup, no restore.
> Blast radius: Medium (backup/export contract work).

> **STORE-I2: Data written by the application's own UI/API must not be
> lost by the application's own backup.**
> Supporting: STORE-014 (tracked) is re-derivable; STORE-001/002 are
> backed up.
> Contradicting: STORE-015 is written by API-021/022 yet invisible to
> every export.
> Blast radius: Small-Medium.

> **STORE-I3: Derived indexes must be rebuildable from their declared
> canonical source.**
> Supporting: STORE-012 reindexes from STORE-002 (LIFE-008); matches
> ARCHITECTURE.md "acceleration layers" rule.
> Conflicts: none found. This one is already satisfied.

> **STORE-I4: Per-person state boundaries must be explicit at write
> time, not derived per request.**
> Supporting: `_user_paths` single source (api.py:318).
> Contradicting: vault/apps/reminders/sessions/discovery/reconciler
> remain global while identity implies multi-person future.
> Blast radius: Large if adopted fully (that is the known finish-line
> isolation gap, honestly recorded in ARCHITECTURE.md).

---

# 4. Cross-Cluster Collisions

| # | Collision | Surface IDs | Current behavior | Why it matters |
|---|---|---|---|---|
| C1 | Auth × tools | AUTH-004 vs TOOL-029 | API world writes need step-up + principal; the tool executor mutates World with a model-supplied `approved` boolean and no principal/step-up in the loop | Two approval vocabularies for the same mutation class; the weaker one is reachable by the model |
| C2 | Tools × persistence | TOOL-025/026, STORE-001, LIFE-009 | Tool writes mutate the per-request World; no `save_world` → mutation evaporates with the request | The brain reports success for state that never lands |
| C3 | Tools × reminders | TOOL-027, TOOL-019, STORE-006, API-067 | Proposal executor no-ops; tool read bypasses Scheduler | Reminders appear in tool narratives but never exist as data |
| C4 | Identity × storage | IDENT-007, STORE-003/006/007, STORE-012 | In multi mode, world/journal/prefs are per-person but vault, apps, reminders, FTS index, sessions are global | "Whose memory is this?" is unanswered for most durable state |
| C5 | Identity × tools | IDENT-005/006, TOOL-000 | Chat/tool loop never receives the request's principal; agent scopes unused in the loop | A scoped agent token could drive the same chat loop a person can |
| C6 | Auth × vault | AUTH-005, API-064 vs API-075..077 | Vault value GET accepts loopback OR private peer; world writes accept the same; but vault set/delete/lock skip step-up entirely | Secret mutation is gated *less* than ordinary intent writes |
| C7 | Storage × backup | STORE-003/005/006/007/015/018/019/010 vs CLI-008/API-028 | backup_payload covers world+journal only | A "restored" instance has no vault, no users, no connections created via UI, no reminders |
| C8 | Providers × identity | CONN-001/002 vs IDENT-007 | All provider connections and native configs are instance-wide; no per-person scoping exists anywhere | A second person inherits the first person's provider credentials/urls |
| C9 | Providers × tools | PROV-015 vs TOOL-020..023; PROV-012 vs TOOL-008..011 | Tools construct providers from env directly instead of resolving via Registry slots | Provider substitution/degradation semantics don't reach tool reads |
| C10 | Providers × capability vocab | app.py vs provider_schemas.py vs api.py descriptions | Three partial capability lists (registry 18 + runtime additions; schemas 7; descriptions dict) | Manifest, connections overview, and status can disagree about what exists |
| C11 | Updates × API | API-029 vs PROV-010 | /api/updates builds an UpdateManager and ignores the registry's native-updates provider | Manifest says update_discovery is healthy; the API surface can be not_configured (or vice versa) |
| C12 | Step-up × journal supersede | API-007, JOURNAL-003, TOOL-024 | Human correction requires step-up + journal APPROVAL event; brain journal write requires neither | Model draft has weaker gate than the human path it imitates |
| C13 | Auth × boot | AUTH-006, STORE-010, DEPLOY-001 | data/.env token overrides compose env at boot; deleting the file is the documented way back | An operator who deletes .env while setup-complete exists has no re-arm path short of deleting the marker |
| C14 | Tools × journal search | TOOL-004 vs JOURNAL-008/API-016 | Tool search calls a nonexistent method (guarded) → always empty; API FTS path works | Brain cannot find what the person's memory search finds |
| C15 | Media × connections overview | CAP-023, API-020, CONN-002 | Overview computes media "configured" from config keys, while live media config lives in the connections array | Overview may report media unconfigured while media works |
| C16 | World policy × tool writes | WORLD-003/006, TOOL-025/026 | check_policy/MutationDenied gate only set_policy/promote_lore/install_pack; intent/fact tools never consult content policies | A cemented deny policy does not stop a brain fact/intent write |
| C17 | Secrets × crypto | SECRET-003, API-061 status | Vault API/UI report `encrypted: true` unconditionally; base64 fallback without the crypto extra | Status vocabulary (DOMAIN-005, honest statuses) contradicted at the secret layer |
| C18 | Sessions × API gate | STORE-004, AUTH-002 vs AUTH-001 | Every login writes a session that protects nothing | Users may believe logging in secured the API |
| C19 | Setup × recovery | STORE-009, STORE-010, API-002 | Lost token post-setup: .env is authoritative but if lost, setup re-run is 409-blocked by the marker | Break-glass requires manual file surgery, contrary to the recovery contract |
| C20 | Providers × per-request world | LIFE-009, PROV-026, TOOL-007 | Every route rebuilds Registry and reloads World; tools add provider subprocess calls per invocation | Consistency is easy (fresh state), but subprocess fan-out per tool call is the cost; documented, listed for completeness |

---

# 5. HUMAN DECISIONS

## Decision D1 — Authentication convergence

**Question**
Should browser session/OIDC authentication resolve into the same
`Principal` used by bearer-authenticated API requests?

**Current surfaces**
`AUTH-001`, `AUTH-002`, `AUTH-003`, `AUTH-008`, `IDENT-001`,
`IDENT-003`, `API-073`, `STORE-004`, `NAV-004`

**Option A**
Complete the session path: `require_auth` accepts a valid session and
resolves its principal through the IdentityStore, making OIDC a real
sign-in for the SPA.

**Option B**
Keep bearer as the only API credential and position session/OIDC as
front-door-only (reverse proxy territory), documenting that sessions
grant nothing beyond the SPA shell.

**Option C**
Retire the in-app session/OIDC code until the finish-line provider-
neutral auth seam is built.

**Existing architecture appears to favor**
A: `identity.py` is explicitly built as "the single seam", and
ARCHITECTURE.md's finish line says authentication becomes
provider-neutral at the application seam with `require_auth` staying
the seam.

**Blast radius**
Large (touches every protected route, login UI, and the multi-user path).

## Decision D2 — Step-up meaning

**Question**
Is step-up an IP/header policy (today) or a credential event (fresh
re-auth, time-boxed, the finish-line wording)?

**Current surfaces**
`AUTH-004`, `AUTH-005`, `AUTH-008`, `UI-018`, every require_step_up
route in the auth matrix.

**Option A**
Make the session grant (AUTH-008) the semantic and require
`require_step_up` to consult it (loopback keeps a documented dev
exception).

**Option B**
Keep the IP/header model and formally document it as the contract,
retiring the session grant.

**Option C**
Both: accept either a fresh grant or the header, with the grant winning
once implemented.

**Existing architecture appears to favor**
The finish line (strong step-up, verified) and the Play-Nice
participation-not-authority framing favor a credential event; the
Docker-loopback reality favors an explicit, visible exception.

**Blast radius**
Medium.

## Decision D3 — Brain approval authority

**Question**
Who is allowed to approve a brain write proposal — the model loop
(today), the human through the chat reply, or a dedicated approval
surface?

**Current surfaces**
`TOOL-024..029`, `CHAT-001`, `API-010`, `API-007`, `JOURNAL-003`,
`WORLD-001/002/006`.

**Option A**
Persist proposals (new store or journal events) and require a
person-authenticated approval call before TOOL-029 will execute; the
loop may not self-approve.

**Option B**
Keep model-approval for low-risk writes (journal notes) and gate
world writes behind the same propose→approve→act pattern the Projects
screen uses.

**Option C**
Remove write tools until durable approval exists.

**Existing architecture appears to favor**
The propose→approve→act pattern already implemented twice in the API
(API-007, API-035), with the Play-Nice participation-not-authority
rule and the HUMAN_RELIABILITY_CONTRACT behind it.

**Blast radius**
Medium-Large (tool loop, chat UI, possibly a new store).

## Decision D4 — Tool write persistence boundary

**Question**
Should brain-executed world mutations (facts/intents) persist through
the same `save_world` path as API writes, and should the tool loop
operate on the same per-request World the API uses?

**Current surfaces**
`TOOL-025`, `TOOL-026`, `WORLD-001`, `WORLD-002`, `STORE-001`,
`LIFE-009`, `API-075/076`.

**Option A**
Executor saves world + journals the event with proposal/provenance IDs
(making the chain identical to the daily loop's persistence).

**Option B**
Restrict tool writes to journal-only (observations), leaving
facts/intents to human surfaces.

**Existing architecture appears to favor**
Option A's shape is implied by TOOL-024 already journaling; but the
policy gate question (C16) must be answered either way.

**Blast radius**
Small (one executor).

## Decision D5 — Update system consolidation

**Question**
Should update *discovery* (native-updates provider, CFG-004) and the
update *state machine* (UpdateManager/ComposeUpdateProvider) be one
system or remain two with a documented division?

**Current surfaces**
`CAP-008`, `PROV-010`, `PROV-027`, `API-029`, `CLI-018`,
`STORE-008`, `STORE-014`.

**Option A**
Single pipeline: UpdateManager consumes NativeUpdatesProvider's
sources; one store, one journal vocabulary.

**Option B**
Keep both: discovery as passive capability status, UpdateManager as
the only mutation path (document that API-029 intentionally reads only
the manager).

**Blast radius**
Small-Medium.

## Decision D6 — Media into the Registry?

**Question**
Should media become a registered capability with its provider slot
managed by build_registry, or remain a deliberate bypass with one
canonical builder?

**Current surfaces**
`CAP-023`, `PROV-015`, `API-053..057`, `TOOL-020..023`,
`CONN-001/002`, `provider_schemas`.

**Option A**
Register media in build_registry (single engine instance, connection
manager owns config).

**Option B**
Keep bypass, collapse to one builder function used by both API and
tools.

**Existing architecture appears to favor**
The provider-neutral contract suggests A; the current code suggests B
was the pragmatic choice.

**Blast radius**
Small-Medium.

## Decision D7 — Scheduler as capability

**Question**
Should the Scheduler be registered as the `scheduler` capability
provider (making API-067 and TOOL-019 go through the Registry), or
should the capability be retired from the vocabulary until a provider
exists?

**Current surfaces**
`CAP-013`, `LIFE-004`, `API-067`, `TOOL-019`, `TOOL-027`, `STORE-006`.

**Option A**
Register a SchedulerProvider; reminders API/tools read through it.

**Option B**
Drop CAP-013 from STANDARD_CAPABILITIES until real.

**Blast radius**
Small.

## Decision D8 — Multi-user scope enforcement

**Question**
Should agent scopes ({read, write, journal, apps}) be enforced on
routes, or should agent tokens be restricted to person-only surfaces
plus a read subset until scopes are real?

**Current surfaces**
`IDENT-005`, `IDENT-006`, `_require_person`, `AUTH-007`, `API-071`.

**Option A**
Enforce scopes in require_auth/step-up (fail closed for missing scope).

**Option B**
Restrict agent creation to read-only scopes until enforcement exists.

**Existing architecture appears to favor**
The narrow-scope fail-closed wording already in `_require_person`'s
docstring.

**Blast radius**
Medium (identity admin + every agent consumer).

## Decision D9 — Backup contract scope

**Question**
Is `backup_payload` allowed to remain world+journal only (with the
recovery plan documented as external), or should the app own a fuller
instance archive including vault metadata, users, connections.local,
reminders, apps, discovery, and reconciler state?

**Current surfaces**
`CLI-008`, `API-028`, `STORE-001..021` (STORAGE-MATRIX backup column),
`ARCHITECTURE.md` export contract.

**Option A**
Keep the current minimal contract; document every excluded store as
operator responsibility.

**Option B**
Extend the payload behind an opt-in flag with explicit secret rules
(vault values never serialize; vault metadata can).

**Existing architecture appears to favor**
The current contract is explicit in ARCHITECTURE.md; the gap is
recorded, not accidental.

**Blast radius**
Medium.

## Decision D10 — Secrets write gate

**Question**
Should vault set/delete/lock require the same step-up gate as world
writes, and should the loopback/private-peer exception be documented
as the permanent local-trust rule?

**Current surfaces**
`API-062`, `API-063/064`, `AUTH-004`, `AUTH-005`, `SECRET-001`,
ARCHITECTURE.md's recorded vault boundaries.

**Option A**
Align secret writes with world writes (step-up), keep the peer rule
documented.

**Option B**
Keep bearer-only secret writes, documenting vault as a deliberately
lower-friction surface.

**Existing architecture appears to favor**
No clear signal; ARCHITECTURE.md records the current restriction
without endorsing it.

**Blast radius**
Small.

## Decision D11 — SOPS scaffolds' fate

**Question**
Keep SopsBroker/SOPSVaultAdapter as the future replaceable-provider
path, or remove them until a connection flow exists?

**Current surfaces**
`PROV-029`, `PROV-030`, `SECRET-004/005`, `CAP-003`.

**Option A**
Keep as dormant machinery (they are the provider-neutral proof).

**Option B**
Remove until used (smaller surface, honesty about what exists).

**Blast radius**
Small.

## Decision D12 — Discovery/reconciler home-directory state

**Question**
Should STORE-018/019 move under PW_DATA_DIR (backed up, per-instance)
or stay in `~/.config` as machine-level state?

**Current surfaces**
`STORE-018`, `STORE-019`, `PROV-013`, `PROV-014`, `DEPLOY-001`
(volume-backed data dir), `API-050/051` (writes to home dir from a
container).

**Option A**
Move under data dir (consistent with "data/ is private runtime
state", survives compose volumes, included in backup decisions).

**Option B**
Keep home-dir placement for multi-instance/multi-user machines;
document as outside-backup.

**Blast radius**
Small-Medium (container volumes currently do NOT include ~/.config —
discovery writes inside the container are lost on container recreation
today, which is an operational fact worth weighing).

---

# 6. STRAIGHTFORWARD DEFECTS

| Surface IDs | Defect | Why unambiguous |
|---|---|---|
| TOOL-004 / JOURNAL-002 | `search_journal` calls `journal.search(query)`, which does not exist on `Journal`; the hasattr guard makes the tool always return `entries: []` with status healthy | Method absent from Journal's API (grep: no `def search`); guarded call cannot succeed |
| TOOL-025/026 / TOOL-029 / STORE-001 | Intent/fact writes mutate the per-request World but never call `save_world`; the executor reports "executed" | tool_registry.py `_execute_approved_write` has no save; contrast with API-075/076 which always save |
| TOOL-027 / STORE-006 | `propose_reminder` executor marks the proposal "executed" while writing nothing to reminders.json or Scheduler | `_execute_approved_write` ptype=="reminder" branch returns ok with no mutation |
| TOOL-028 / PROV-014 | `propose_reconciler_apply` reports "executed" with a note that no apply occurred | explicit in code; success status contradicts its own note |
| TOOL-018 / SECRET-001 | `inspect_vault_status` and API-061 hardcode `encrypted: true` regardless of base64 fallback | vault.py exposes `warning` property for exactly this; callers ignore it |
| TOOL-028/TOOL-013 / PROV-014 | Tools read `reconciler._desired`, a private attribute | private-attr access across module boundary; diff tool admits observed state is unavailable |
| TOOL-019 / STORE-006 | Tool reads reminders.json via `PW_DATA_DIR` env instead of the Scheduler/data_dir captured at create_app | env may disagree with the app's actual data_dir; API uses the singleton |
| TOOL-024 provenance | Journal write from brain-tool carries no proposal id, approval, or chat provenance | `journal.record("observation", text, source="brain-tool")` only |
| AUTH-008 / AUTH-004 | `POST /api/auth/step-up` grants step_up_until that `require_step_up` never reads | grep: `has_step_up`/`step_up_until` referenced only in auth.py/auth_routes |
| C13 / STORE-010 | `_reconcile_boot_token` ignores malformed/missing PW_API_TOKEN lines silently (fail-toward-deploy) while setup UI assumes success | code comments acknowledge; UI copy does not |
| API-064 doc vs code | Error text says "loopback-only" but the check accepts any Python-classified private address | same function contains the broader ip.is_private branch |
| CAP-023 / CONN-001 | `connections_overview` computes media config from `config["media"]["providers"|"adapters"]` while media adapters actually live in the `connections` array | shape mismatch between overview detection and STORE-014/015 layout |
| TOOL-017 / metadata | `run_discovery` registered `read_write="read"` but persists feedback/sources to STORE-018 | its own `_save()` calls |
| TOOL-000 / TOOL-029 | `_proposals` is module-global, shared across concurrent requests in one process with no locking | plain dict, `_proposal_counter` global |
| TOOL-029 | `requires_step_up=True` on the tool is metadata only; no enforcement path exists in the tool loop | invoke() never checks it |
| API-012 doc | Route docstring in older docs claimed public; current code correctly requires auth — the ARCHITECTURE table still describes the old state in one line | docs/code drift, no decision needed |
| UI-023 / DEPLOY-005 | When dist is missing, 503 page instructs building the frontend, but `frontend/dist/` is gitignored and CI builds it separately — first-run compose users get the 503 until a build step runs | matches test_dist_safety expectations; not a choice, a packaging note |
| PROV-012 native_lab | `native_lab` connection type registers `settings_validation`/`service_health` under names that shadow the STANDARD capabilities' meaning (settings_validation is "native lab settings", not validation against intent) | naming collision visible in manifest |
| LIFE-002 | build_registry runs on every request; provider subprocesses (native lab discovery etc.) are cheap, but `ChatProviderRegistry`-style caches are absent — repeated `provider_for` health checks per request | per-request cost, no correctness risk |

---

# 7. One-Screen Human Brief

**3 biggest architecture choices**
1. **D1 — Auth convergence:** make session/OIDC resolve into the same
   Principal as bearer, or formally demote sessions to front-door-only.
   Everything downstream (vault, step-up, multi-user) depends on it.
2. **D3 — Brain approval authority:** human-gated durable proposals vs
   model-supplied approval booleans; this defines what "the assistant
   changed my world" means.
3. **D9 — Backup contract:** world+journal-only backup vs app-owned
   fuller recovery (vault/users/connections/reminders/interests).

**5 unambiguous defects**
1. TOOL-025/026 world writes don't persist (`save_world` missing).
2. TOOL-027 reports executed, writes no reminder.
3. TOOL-004 journal search calls a nonexistent method → always empty.
4. AUTH-008 step-up grant never consumed by `require_step_up`.
5. TOOL-028 reports "executed" with an explicit no-apply note.

**3 most dangerous source-of-truth splits**
1. Two credential systems (bearer vs session/OIDC) with one gate.
2. Two update systems (NativeUpdatesProvider vs UpdateManager) with
   different stores and journals; `/api/updates` shows only one.
3. User-authored durable state outside backup: connections.local.json,
   discovery.json, reconciler desired, users.json, reminders, vault.

**3 things that should NOT be redesigned**
1. The propose→approve→act + step-up pattern already used by
   API-007/API-035 — it is the house style and it works.
2. `require_auth` as the single principal seam (IDENT-001/003) —
   extend it, don't replace it.
3. The append-only journal + derived FTS index split (STORE-002 →
   STORE-012) — it satisfies the rebuildability contract exactly.

**Recommended order for human review**
1. D1/D2 (auth convergence + step-up meaning) — one combined session.
2. D3/D4 (brain approval + persistence) — one combined session.
3. D9/D12 (backup + home-dir state) — recovery contract session.
4. D5–D8, D10, D11 — smaller consolidations, any order.
5. Defect list (Part 6) as a single implementation pass afterwards.