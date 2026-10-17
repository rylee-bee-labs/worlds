# Wiring Readiness — Project Worlds

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`.project/CURRENT.md`](../../.project/CURRENT.md)) · **Read this if:** you need the dated SHA `60823ae` GREEN/YELLOW/RED assessment for provenance · **Superseded by:** the running code and [`.project/CURRENT.md`](../../.project/CURRENT.md).

**In short:** a GREEN/YELLOW/RED/GRAY read on each subsystem plus
default-provider candidates, taken at SHA `60823ae` before the 2026-09-22
interface flip. It is a past assessment, not current state — the rows
naming `frontend/`, `PW_FRONTEND*`, or the pre-flip screen set describe
that earlier tree. No wiring was performed in this pass.

Assessment for the next pass: **find what is not wired, wire it,
establish default local providers, make API/runtime coherent
end-to-end.** Landed on `main` via PR #50 (merge `1701476`).

Legend: **GREEN** fully wired · **YELLOW** partial / bypass / duplicate ·
**RED** broken / stubbed / orphaned · **GRAY** intentionally deferred.

## Truth-state convention

- **BASE** — true on the committed inventory base (`60823ae`).
- **KNOWN UNMERGED FIX** — a fix exists in another worktree/lane but is
  not integrated into the base.
- **CURRENT** — true in the authoritative branch being evaluated.

A KNOWN UNMERGED FIX does not turn a BASE defect GREEN; it is recorded
as a pending integration.

Detail for every non-GREEN subsystem is below the table.

## Readiness

| Subsystem | Status | Reason | Next action |
|---|---|---|---|
| Auth | GREEN | Bearer/session/OIDC converge on one `Principal`; step-up consumes the principal-bound session grant (D1–D3). | None. Keep the seam. |
| Identity | YELLOW | Multi-mode foundation: world/journal/prefs per-user; apps, vault, reminders, proposals stay instance-global. Legacy `UserManager` store unused. | Decide per-user boundaries; retire `users/<id>.json`. |
| World | GREEN | Container + mutation gates + step-up writes work. | None. |
| Journal | GREEN | Append-only, supersede, audit/story, FTS bridge. | None. |
| Brain (reasoning + templates) | YELLOW | Providers exist; default none; live Ollama/OpenCode lack `chat_with_tools`; context double-derives projects/git. | Port tool-calling; pick a default brain (ADR 0002). |
| Tools | YELLOW | BASE: write-safety is coherent (durable proposals, server-held step-up approval, execution blocked from the model); `TOOL-013` desired-only and `TOOL-017` mislabelled. | Add a proposals UI; fix the two labels. |
| Proposals | YELLOW | BASE: durable store + approve/reject/execute step-up API + durability tests work; instance-global; no frontend review UI. | Namespace per user; add a review UI. |
| Providers | YELLOW | Registry exists, but ~35 API handlers bypass it; capabilities have competing implementations. | Converge reads through `provider_for`; pick one authority per capability. |
| Connections | GREEN | `ConnectionManager` merges tracked + local config; writes go local. | None (rollup divergence removed). |
| Media | YELLOW | Works, but bypasses the Registry; two builders; never a registered capability. | Register a `media` capability/provider; single builder. |
| Reminders | GREEN | Scheduler + persistence + step-up API; tool reads via Scheduler. | Fix proposal executor (Tools). |
| Projects | YELLOW | Works via external `agent-sync` binary; frontend health always "Healthy". | Fix frontend health; decide agent-sync optionality. |
| Source Control | YELLOW | Native local Git reads work; API bypasses the registry; enrichment needs `gh`. | Route reads through the provider; make forge enrichment optional. |
| Discovery | YELLOW | Works via connection only; feedback is process-local; `_discover_api` is a stub. | Persist feedback; pick a default source. |
| Reconciler | YELLOW | Observe-only; no apply; `diff`/`propose` read a body on GET. | Add apply path or mark observe-only; fix HTTP semantics. |
| Updates | YELLOW | Two systems (`updates.py` used; `native_updates` registered, unused); apply/rollback CLI-only; rewrites tracked compose. | One authority; explicit intent before mutating tracked infra. |
| Deployment | GRAY | Intentionally optional/deferred: `NativeDeploymentProvider` is observe-only; adapters have no live deploy caller. | Defer; revisit with the updates authority. |
| Vault | YELLOW | Native Vault works and **fails closed** without the `cryptography` extra (no base64 fallback; corrected 2026-09-15); no step-up on secret ops; `GET` accepts private peers. | Step-up secret ops; true-loopback only. |
| Settings (prefs/sections/apps) | GREEN | Validated prefs, sections, apps registry, step-up writes. | None. |
| Chat | YELLOW | Live; Ollama tool-calling broken; duplicate builder; no streaming; history not persisted. | Remove orphan; port tool-calling; decide persistence. |
| Assistant / companion | YELLOW | Companion prefs + edge trigger exist; theme-pack state machine not runtime-resolved. | Wire theme packs or defer. |
| Notifications | YELLOW | Optional: observe works; no in-app `send()` path; health says `unavailable` (not `not_configured`) on zero targets. | Wire a send path or declare observe-only; fix health. |
| Frontend screens | YELLOW | Broad live coverage. BASE broken: Today journal field (ORPH-18) and Projects health (ORPH-19). Today has a KNOWN UNMERGED FIX; Projects is broken in the lane too. Step-up UX half-wired; dead `ChatScreen`. | Integrate the lane fix; fix Projects; wire step-up; prune. |
| CLI | YELLOW | All commands active; registry/config/dry-run divergences from API. | Unify registry + canonical readers. |
| API | YELLOW | No dead routes; large bypass cluster; one duplicate alias. | Converge bypasses in the wiring pass. |
| Storage | YELLOW | Canonical stores exist; most are unbacked; multi-writer `world.json`; orphan `executions.json`. | Define backup coverage; per-user namespacing. |
| Lifecycle (create_app/scheduler/init) | GREEN | App, lifespan, scheduler thread, zero-provider init all work. | None. |
| Exports / Backup | YELLOW | Four contracts work; backup covers global world+journal only. | Expand recovery plan. |

## Detail (non-GREEN)

### Identity — YELLOW
**Exists:** `identity.py` single/multi resolution, hashed tokens, admin
routes, display-name, per-user world/journal/prefs paths.
**Missing:** per-user apps/vault/reminders/proposals/chat; no household
isolation; legacy `user.py::UserManager` unused.
**Canonical path:** `identity.py` (not `user.py`).
**Risk:** medium (privacy boundary).
**Action:** define ownership boundaries; retire the legacy store.

### Brain — YELLOW
**Exists:** Ollama/OpenAICompat/OpenAI/Anthropic/OpenCode providers,
TemplateRegistry, context builder.
**Missing:** live-class `chat_with_tools`; a default reasoning provider;
single context derivation.
**Canonical path:** `chat_registry.py` → `Registry.provider_for("reasoning")`.
**Risk:** medium.
**Action:** port tool-calling; apply ADR 0002 default; de-duplicate context.

### Tools — YELLOW
**Exists:** 29 registered tools; read tools work; proposal tools create
durable pending proposals; reminder execution persists through
`Scheduler`; reconciler execution honestly returns `unsupported`;
execution tools are structurally blocked from the model
(`tool_registry.py:96-127`).
**Missing:** the `/api/proposals*` lifecycle has no frontend consumer;
`TOOL-013 inspect_reconciler_diff` returns desired-only; `TOOL-017
run_discovery` is labelled read while it fetches and can persist.
**Canonical path:** `proposals.json` store + `/api/proposals/*` API
(step-up).
**Risk:** low (write-safety is already enforced server-side).
**Action:** add a proposal review UI; fix the two labels.

### Proposals — YELLOW
**Exists:** durable store (`configure_proposal_store`; atomic
`data/proposals.json`), server-held approval evidence (`approved_by`/
`approved_at`/`approval_evidence`), `GET/POST /api/proposals*` step-up,
and durable lifecycle tests (`tests/test_proposal_durability.py`). The
chat tool loop creates proposals through the same durable store.
**Missing:** per-user namespacing; a frontend review UI.
**Risk:** medium.
**Action:** namespace per user; optional review UI.

### Providers — YELLOW
**Exists:** Registry, contracts, status/observe, manifest.
**Missing:** uniform use; the ~35 bypass handlers (media, lab,
native-lab, discovery, reconciler, source-control, updates, ingress,
projects, enrichment).
**Canonical path:** `Registry.provider_for(capability)`.
**Risk:** medium.
**Action:** converge each bypass; one authority per capability.

### Media — YELLOW
**Exists:** `NativeMediaEngine` + Plex/Sonarr/Radarr/Lidarr adapters.
**Missing:** registration; single builder.
**Risk:** low.
**Action:** register `media`; one builder taking `ConnectionManager`.

### Source Control — YELLOW
**Exists:** `NativeGit` baseline, status/history/refresh, `gh` enrichment.
**Missing:** registry-mediated reads; forge provider is machinery only.
**Risk:** medium.
**Action:** route reads through the provider; keep `gh` optional.

### Discovery — YELLOW
**Exists:** `NativeDiscovery`, sources/interests/discover, step-up writes.
**Missing:** a default source; persisted feedback; real API-source support.
**Risk:** low.
**Action:** persist `_feedback`; ship one local default source.

### Reconciler — YELLOW
**Exists:** observe/diff/propose over desired state.
**Missing:** apply; observed-state diff.
**Risk:** medium.
**Action:** add apply through the provider or mark observe-only; fix GET.

### Updates — YELLOW
**Exists:** `UpdateManager` CLI state machine; `native_updates` provider.
**Missing:** one authority; non-CLI apply; safe handling of tracked compose.
**Risk:** high (mutates tracked infra).
**Action:** unify; require explicit intent before writing `compose.yaml`.

### Deployment — GRAY
**Exists:** `native_deployment` + compose/systemd adapters (observe).
**Missing:** any live deploy caller. This is treated as optional/
deferred, not broken.
**Risk:** low.
**Action:** revisit alongside the updates authority; otherwise leave
observe-only with an honest `not_configured`.

### Vault — YELLOW
**Exists:** native `Vault` (`vault.enc`), unlock/lock/names/set/delete;
it fails closed without the `cryptography` extra (no base64 fallback) —
corrected 2026-09-15 against the finish pass.
**Missing:** step-up on secret ops; true-loopback-only value get;
per-user isolation.
**Risk:** high (secret boundary).
**Action:** step-up secret ops; fix peer check.

### Chat — YELLOW
**Exists:** live chat route, providers list, tool loop.
**Missing:** Ollama tool-calling; stream; history persistence; orphan removal.
**Risk:** medium.
**Action:** see Brain/Tools.

### Assistant / companion — YELLOW
**Exists:** companion prefs vocabulary, edge trigger, World Keeper.
**Missing:** runtime theme-pack state resolution.
**Risk:** low.
**Action:** wire theme packs or defer.

### Notifications — YELLOW
**Exists:** `NativeNotificationsProvider` + webhook/ntfy adapters;
observe works; honest status when nothing is configured.
**Missing:** any caller for `send()`; health says `unavailable` rather
than `not_configured` on zero targets.
**Risk:** low (optional capability).
**Action:** wire a send path or declare observe-only; fix health.

### Frontend screens — YELLOW
**Exists:** 13 routes across the product.
**BASE defects:** Today journal field (ORPH-18) — `entry.text` vs the
API's `summary`; Projects health (ORPH-19) — `repo.ok` on a type with
`error`, always "Healthy". Today has a **KNOWN UNMERGED FIX** in the
`docs/current-product-refresh` worktree; Projects is broken in that
lane too.
**Missing:** interactive step-up in writes other than Vault/Settings/
Connections; pruning of dead code (`ChatScreen`, hooks, helpers).
**Risk:** medium (user-visible correctness).
**Action:** integrate the lane Today fix; fix Projects; drive step-up
through `POST /api/auth/step-up`; delete dead code.

### CLI — YELLOW
**Exists:** 18 commands, JSON envelope.
**Missing:** unified registry build; canonical config merge in
`framework validate`; correct dry-run in `daily`; supersede-aware
`journal`; principal-scoped `prefs`.
**Risk:** medium.
**Action:** share registry/reader construction with the API.

### API — YELLOW
**Exists:** 116 handlers, no dead routes, one alias.
**Missing:** canonical-service delegation across the bypass cluster.
**Risk:** medium.
**Action:** the core of the next pass.

### Storage — YELLOW
**Exists:** canonical JSON/NDJSON/enc stores.
**Missing:** backup coverage; per-user namespacing; orphan cleanup.
**Risk:** high (data loss).
**Action:** define backup coverage; remove `executions.json`.

### Exports / Backup — YELLOW
**Exists:** settings/world/story/backup contracts.
**Missing:** full-instance recovery.
**Risk:** high.
**Action:** extend recovery plan (vault, identities, user trees).

## Default local provider candidates (Phase 15)

Do **not** implement in this pass. "Local" = works on a fresh install
with no remote service.

| Capability | Current | Recommended local default candidate | Why | Blocker |
|---|---|---|---|---|
| World persistence | core `world.json` | core `world.json` (already default) | Durable, inspectable, provider-neutral | None |
| Journal + search | core `Journal` + `native-memory` FTS5 | core `Journal` + `native-memory` (already default) | Works offline; index rebuildable | None |
| Brain / model | none (zero-AI boot) | **DEFAULT NOT CHOSEN YET** — candidates: local Ollama; ADR 0002 suggests Qwen3 1.7B / LFM2.5. Do not hardcode. | No decision until tool-calling works and candidates are benchmarked | Live `OllamaChat`/`OpenCodeChat` lack `chat_with_tools` (ORPH-03) |
| Embeddings | none (FTS5 only) | keep **FTS5** as default; add a local embedding provider as enrichment | Avoid a hard vector dependency; FTS5 is local | No embedding provider implemented |
| Media | none | none local (external Plex/*arr by nature) | Media sources are inherently external services | No local filesystem media provider exists |
| Reminders / scheduler | core `Scheduler` | core `Scheduler` (already) | Local, persistent, threaded | None |
| Source control | `NativeGit` (local `git`) | `NativeGit` (already) | Local git is the native baseline | Needs configured search paths |
| Updates | `updates.py` compose (CLI) | unify onto `native-updates` with a local compose adapter | One authority; local docker compose | Two systems; mutates tracked compose |
| Deployment | `native-deployment` (observe) | `native-deployment` compose/systemd adapter | Local, no remote | No apply path |
| Vault / secrets | native `Vault` (`vault.enc`) | native `Vault` **with the crypto extra required** | Local, encrypted, provider-neutral | Fails closed without `cryptography` (no fallback) |
| Discovery | none | `native_discovery` with a **local file/OPML source** | Fully local first-run | No default source; feedback not persisted |
| Reconciler | `native-reconciler` (observe) | `native-reconciler` (already) | Local desired state | No apply; may stay observe-only |
| Chat | none | follows the Brain decision (not chosen yet) | Local conversation | Tool-calling; history persistence |
| Notifications | `native-notifications` (uncalled) | local **ntfy/webhook** target | Local-first notification | `send()` has no caller |
| Projects | `agent-sync` (external binary) | none required on a fresh install; degrade honestly | Avoid requiring a binary | `agent-sync` may be absent |

## Default brain

```text
NOT CHOSEN YET
```

ADR 0002 names Qwen3 1.7B with an LFM2.5 fallback, but that is not a
decision for this pass and must not be hardcoded. Prerequisite sequence
for the wiring pass:

1. Repair tool-calling on the live chat providers (`OllamaChat` /
   `OpenCodeChat` lack `chat_with_tools`; the orphan `chat.py` copy has
   it) — ORPH-03.
2. Benchmark local candidates against the actual tool/chat workload.
3. Then choose the default brain (and record it in an ADR / decisions).

## Proposed full-restore boundary

Not implemented in this pass. A "full instance restore" plan should
preserve durable instance truth:

```text
world.json, journal.ndjson            RESTORE (authoritative)
per-user trees (world/journal)        RESTORE
users.json (identities)               RESTORE
vault.enc                             RESTORE (secret portability — security-sensitive; see caveat)
reminders.json, apps.json             RESTORE
proposals.json                        RESTORE
connections.local.json                RESTORE (private overrides; secret-free by policy)
oidc.json                             RESTORE config only (client secret stays externally managed)
discovery.json, reconciler/lab desired RESTORE (user-authored state)
theme packs, template-sources         RESTORE (user-owned state)
sessions.json                         OPTIONAL (ephemeral; may be dropped on restore)
memory.fts5.db                        REGENERABLE (rebuild from journal)
updates-session.json                  REGENERABLE (operational session)
```

Caveat (for the implementation pass, not decided here): vault and any
external secret material require an explicit secret-portability decision
(encryption at rest, passphrase handling, whether secrets belong in a
backup artifact at all). Do not treat `vault.enc` as portable by default.

## Media default

Confirmed: media remains an **optional external capability**. Plex,
Sonarr, Radarr, and Lidarr are external integrations; there is no
mandatory local media provider on a fresh install. When unconfigured the
surface must show an honest unavailable/empty state. Do not invent a
filesystem-media provider merely to give every capability a default.

## Remaining human decisions

1. **Adoption manifest authority — RESOLVED 2026-09-15.**
   `.project/contracts/adoption.yaml` (pin `0cee065`, v0.6.0) is the
   single manifest: it is declared by `.project/project.yaml`, used by
   the documented session workflow, and matches the Play-Nice
   project-context layout. The duplicate `.contracts/adoption.yaml`
   (pin `1c05de4`) was removed and `AGENT_CONTRACTS.md` repointed. See
   `REPOSITORY-INVENTORY.md` §4 for the reasoning.
2. **Default brain.** Now explicitly deferred (see above): repair
   tool-calling, benchmark, then choose. Not a blocker for this pass.
3. **Vault secret portability.** Whether (and how) `vault.enc` belongs in
   a restore artifact. Security-sensitive; decide in the wiring pass.

## Next wiring order

Derived from reconciled evidence; architecture-level convergence first,
not endpoint whack-a-mole.

```text
P0  Brain + Chat tool-calling coherence (ORPH-03, orphan removal, history/stream decision)
P0  Provider Registry convergence — remove direct bypass construction (media, lab,
      native-lab, discovery, reconciler, source-control, updates, ingress, projects, enrichment)
P0  API canonical-service convergence (drive the bypass handlers through providers/services)
P1  CLI construction convergence with the API (registry, config merge, daily dry-run, journal/prefs)
P1  Frontend runtime defects NOT already fixed in another lane (Projects health; step-up UX;
      integrate the Today lane fix when that lane lands)
P1  Storage + backup/recovery scope (full-restore boundary above; per-user namespacing)
P1  Vault trust/step-up/crypto guarantees (require crypto extra; step-up secret ops; true loopback)
P2  Discovery persistence + default local source
P2  Updates authority (one system; safe handling of tracked compose)
P2  Deployment / Notifications / Reconciler optional capabilities (honest observe-only)
P3  Dead-code cleanup (ORPH-01/02/05, unused frontend hooks/components)
```

## Next task

> Repository inventory, surface documentation, and wiring readiness are
> now reconciled against current code and known unmerged lanes. Project
> Worlds is ready for the full wiring/default-local-provider/API
> convergence pass.