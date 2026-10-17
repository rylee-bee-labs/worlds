# Handoff: front-door approval (2026-10-01)

> **Status:** Owner instruction, recorded verbatim · **Recorded:** 2026-10-01 · **Canonical for:** the owner's approval of PR #231 and the refinements that supersede it where stated.

The text between the markers is the owner's handoff, sections 1–15, unchanged. The "Owner answers" list follows it.

===== OWNER HANDOFF (verbatim, sections 1–15) =====

Worlds Front Door — approval and implementation handoff
Owner: Rylee · Recipient: Claude, implementation orchestrator · 2026-10-01

## 1. Approval, scope and precedence

I approve the front-door product direction in PR #231, with the explicit refinements below. This is authorization to build the new Worlds and carry the implementation campaign through verification and production replacement. It is not another proposal round.

The attached handoff is the owner's next instruction. Record its decisions in the repository before implementing them. Do not treat this document as evidence that a GitHub review, merge or deployment has already happened.

Use PR #231 as the architectural baseline. This handoff supersedes it where stated; security, privacy, accessibility and external-system boundaries remain. In particular:

- Proposal: "No rewrite is needed"; incremental replacement → Approved: A clean application rebuild is authorized. Reuse good code when it fits; compatibility with the obsolete app is not a goal.
- Proposal: Phase 0 only, followed by further phase approvals → Approved: Complete the campaign continuously. Do not ask permission to continue after ordinary milestones.
- Proposal: Every old subsystem gets a replacement before removal → Approved: Required new behavior and security properties must work before production cutover. Obsolete features need no replacement merely to justify deleting them from the new application.
- Proposal: Chat remains reachable while its replacement is built → Approved: Chat is optional and may be absent from the new application.
- Proposal: Governed bindings arrive in Phase 5 → Approved: Authority and durable single-dispatch behavior arrive before any side-effecting integration, including Connect test/run.
- Proposal: Several competing Home drafts → Approved: Instruments and the hierarchy in section 8 are current. Earlier tile-only layouts, Lamplight/Glyph defaults and competing navigation are historical experiments.
- Proposal: Rough LOC and route targets → Approved: Use size as a diagnostic, not a quota. Optimize for comprehensibility and necessary behavior.

Read the current PR head, comments, AGENTS.md, AGENT_POLICY.md, AGENT_CONTRACTS.md, .project/CURRENT.md, the adopted contracts, and relevant security/accessibility/operations documents. Inspect code and deployment evidence before assuming a specification is implemented.

If PR #231 changes materially after this handoff, reconcile the delta before merging. Do not silently treat later text as owner-approved. Land approval status, ADR-0008 and supersession notes through the repository workflow; verify required checks and unresolved review findings. The reviewed proposal head was dbc1218bf2dbf5591f0627a0fbbd4a22e7b9f158; refresh this at execution time.

## 2. What Worlds means

Worlds owns meaning. Providers own mechanics.

Worlds is a small personal front door that gathers a large world without having to contain the whole world.

I am the only human user. Agents use scoped tokens. External services retain authority over their own data and operations.

The stable landmarks are Home · Connect · Memory · Settings. Keep these concepts consistent in UI, APIs, files and code. Packs cannot rename or move them. Personal boards may exist beneath this structure without becoming permanent product landmarks.

The integration model is:

```
Provider → Request → Mapping → Card → Board
                └→ explicit Governed Action binding
```

Do not introduce a competing architecture unless real integration evidence demonstrates a material limitation. Raise that limitation clearly, with evidence and a proposed resolution.

## 3. Working authority and boundaries

Make ordinary engineering and design decisions: structure, filenames, CSS, spacing, Connect subtabs, implementation language organization, tests, obvious field mappings, minor copy and routine refactoring. Record consequential technical choices and continue.

Escalate only changes to product meaning, landmark boundaries, human authority, privacy, security boundaries, external sources of truth, Memory ownership, or a major interaction that contradicts this direction. Destructive changes outside Worlds require separate authorization.

This handoff authorizes conditional replacement of Worlds production after the acceptance gates pass. Use the existing Project Home approval/deployment mechanism where applicable. An operational approval prompt is a transport for owner authority, not a new approval system. Do not bypass a required live approval or invent one for ordinary implementation work.

Use existing secret references and approved resolution paths. Do not expose values, rotate unrelated credentials, or alter sibling repositories and external infrastructure without authorization. If a companion change is needed, document its exact scope and keep independent work moving.

Aggressive deletion is permitted inside obsolete Worlds architecture. It does not authorize deleting Project Home, Sonarr data, media libraries, repositories, homelab services, lore/memory systems or external databases.

## 4. Preserve, then establish a fresh baseline

Verify remote, branch, worktrees, uncommitted work and current origin/main. Preserve unrelated work. Do not reset or force-push over it.

Before implementation, create and verify archive/pre-front-door at the last pre-rebuild source baseline. Record its commit and push the tag so it survives the execution environment. If the tag already exists, inspect it; do not move it silently. If the currently deployed commit differs, record and preserve that exact source reference too.

Capture enough information to reconstruct the old deployment: topology, immutable image/commit identity, service definitions, OIDC requirements, config and secret references, ingress assumptions and external connections. Keep private topology, endpoints, config and data in an approved private location. The public repository gets sanitized instructions and references only. Git preserves source; it does not preserve untracked deployment configuration or runtime data.

Build the replacement separately, with fresh Worlds runtime/configuration. Do not mutate the live installation piecemeal. Delete obsolete code from the new tree rather than creating a museum of legacy routes, schemas, screens and adapters.

Preserve approved art and canon, useful theme tokens, accessibility foundations, Play-Nice contracts, security properties, integration knowledge and relevant journal/event concepts. Do not edit or regenerate protected artwork as part of this rebuild.

## 5. Claude owns orchestration and integration

Use a small implementation team where work is genuinely independent. Claude remains responsible for the final architecture, contract decisions, integration branch, acceptance evidence and deployment ledger.

Suggested lanes, combined or sequenced as needed: Foundation (configuration schemas, runner, mappings, reference provider and storage boundaries); Authority/security (identity, scoped tokens, policy integration, durable dispatch/receipts, confinement and privacy); Experience (responsive shell, Instruments, Connect, accessibility and pack invariance); Memory/integrations (deterministic Memory; real service slices after the foundation contracts stabilize); Review (independently exercise security, failures, accessibility and install/cutover evidence).

Give each worker a bounded task, relevant contracts, allowed paths, dependencies and a definition of done. Use separate worktrees and branches; stage explicit paths. No worker force-pushes shared history, touches another lane's working tree, merges competing contracts or independently deploys production.

Agree on small interface contracts before parallel implementation: config identifiers/schema, result and freshness envelope, action/policy/receipt lifecycle, Memory persistence boundary and card accessibility props. One owner approves shared contract changes. Keep these contracts concise; do not spend weeks designing a generic framework.

Claude integrates coherent slices, resolves conflicts and verifies the combined system. Passing worker tests are not proof that the integrated application works. Persist decisions, current state, gate evidence, blockers and next work in the repository's existing .project/ system so another session can resume without archaeology.

## 6. Small backend and file configuration

Provider: registered connectivity and credential references. Request: method, relative path, parameters, permitted headers/body, assertions, timeout, TTL and response limits. Mapping: translation from external shape to human meaning; descriptive concept metadata, not a giant capability enum. Card: a small set of accessible presentation primitives. Board: composition; Home is a board. Governed Action: explicit executable binding, scope, policy and receipt.

New ordinary API concepts should generally require configuration, not new core Python. Recipes are provider templates plus requests, mappings and suggested cards. Services speaking room/0 remain supported; Worlds calls them services while the upstream contract retains its name. MCP, arbitrary templates and OpenAPI import are later work; OpenAPI import follows the first three proven recipes.

Configuration is documented files. Ordinary interaction is Connect → edit → test → save; power use is YAML/git/bulk edit. UI-created configuration must round-trip without semantic loss. Real config belongs in the private data/config volume; public examples use synthetic endpoints and references.

Validate references and schemas, write atomically, handle concurrent edits visibly, and keep the last valid configuration active after an invalid edit. Reload must not execute an action. Credential, destination or action changes invalidate affected pending authorizations. Mapping is declarative and bounded; it cannot introduce arbitrary code execution. Escape external content and sanitize supported rich text.

Distinguish configuration, disposable caches, durable Memory and durable action receipts. A runtime database is acceptable for durable app records; an invisible UI-only configuration database is not canonical. Use existing lightweight mechanics that fit the contracts.

## 7. One authority path, including Connect

Human UI, assistant and automation use the same governed authority path for executable actions. A saved request is not automatically a tool. Agents discover only explicit governed bindings permitted by their scope; possession of a token is not approval authority.

Connect test/run must not become a write bypass. An unbound read may be tested under owner authentication and privacy/confinement rules; a side-effecting test must use the same governed action and approval path as an ordinary action. Saving, mapping, previewing and importing configuration must never dispatch a write.

Default non-GET/HEAD methods to write-like treatment. GET/HEAD are not proof of harmlessness: known side-effecting endpoints also receive write policy. Sensitive reads still require explicit scopes, privacy policy and step-up where required. Missing approval policy defaults to approval required; missing bindings, permissions or valid authorization deny execution.

Inspect the existing Project Home authority contract first. Reuse its canonical approval authority where it governs an operation; Worlds may own bindings and execution receipts without becoming a second approval authority. Bind authorization to the resolved action version, caller, destination and parameters, with expiry and one-use consumption. Recheck permissions and configuration before dispatch. If the existing authority cannot support a required invariant, raise the concrete contract gap instead of silently creating a substitute.

For side effects: approve → durably consume authorization → dispatch at most once → SUCCEEDED | FAILED | UNKNOWN

Consumption and dispatch claiming must be atomic under concurrency and durable across restart. Record intent before attempting network execution. Disable automatic side-effect retries in clients, workers and recovery paths. After a crash or cancellation, never redispatch an execution that may have reached the provider.

This is an at-most-once dispatch guarantee for Worlds, not exactly-once execution by a remote service. Report FAILED only when evidence supports the claimed failure; a timeout, lost response, ambiguous remote error or interrupted dispatch may be UNKNOWN. Preserve that uncertainty in receipts and UI. A read-only status check may reconcile evidence; it must not replay the write. A retry is a new action with fresh authorization and a clear warning that the earlier action may have completed. Idempotency support strengthens safety but does not authorize automatic replay.

Test competing dispatchers, approval replay/expiry, parameter changes, cancellation, timeouts, lost responses and crashes on either side of durable consumption. Receipts identify caller, action/config version, authority reference, timestamps, dispatch status, outcome and redacted evidence.

## 8. Home: Instruments, with life beside machines

Home must feel like my life has machinery in it, not like my machinery has a dashboard attached to it.

The settled hierarchy is: 1. Greeting and terse briefing: 2 for you · Downloads down · rest quiet. 2. Compact whole-world state strip. 3. Needs you — finite, bounded items that genuinely require my action. 4. Needs a look — stale, degraded, unavailable or noteworthy sources without manufacturing an obligation. 5. Pick up — approximately three relevant threads interrupted because I stopped: a half-configured request, board edit, opened Later item or project context. 6. Your life — Memory, reading, Today, interests, music, discoveries, kept ideas and personal context. 7. Quietly working — healthy machinery with lower emphasis and full legibility.

Pick up is not generic recent history, another inbox, a task manager or a guilt list. Optional integrations do not nag. Not configured is not failure. Unknown is not failure. When a bounded list ends, it ends.

Use Instruments rows with recognizable icons, meaning, appropriate meters, aligned values/units, state and freshness. Meters need text equivalents and must not invent progress. Freeze last-known meters honestly when data is stale. Keep groups and reading order predictable; do not reorder the interface while someone is reading or focused in it.

The whole-world strip gives each source an icon, name, state shape, accessible label and comfortable target. Use shape + word + colour, never colour alone. Canonical states include Healthy, Needs attention, Unavailable, Stale, Unknown and Not configured. Wrap cleanly on phones. Selecting a source opens or jumps to its detail.

Ordinary use outranks customization. Edit Home is secondary and explicit, with move earlier/later, hide/show, supported sizes and undo. Use + Add to Home. Station does not change the user's ordering.

Drill-in follows meaning → current state → detail → freshness → technical evidence → Connect. Technical evidence should be reachable in about two interactions. Raw API mechanics belong in Connect; cards offer View source or Configure source links rather than miniature provider consoles.

Refine layout, density, meters, copy and breakpoints against real service data. Preserve these principles rather than mock pixels. Do not force all content above the fold at the expense of readability.

## 9. Words, warmth and Station

Keep Minimal · Short · Full, default Short. Minimal shows facts: name, value, unit and state. Short adds small meaning phrases and the terse briefing. Full adds explanation and freshness; long detail still belongs in drill-in. Words controls explanation, not authorization disclosure or access to evidence. Density is a separate comfort preference, not another product mode.

Core already has heart: warm language, humane prioritization, continuity, ordinary-life content, typography, restrained identity and specific real details. Do not rebuild personality infrastructure into core to achieve warmth.

Core owns facts and baseline meaning. Packs may re-voice meaning only equivalently; they may freely change flavor. Station may add Sol, crew, lore, static decorative presence, HUD treatment, starfield, illustrations, stickers and optional discoveries. It may not alter landmarks, navigation, card order, functions, factual meaning or accessibility. Reserve decorative space so toggling it causes no layout shifts.

No gamified maintenance, warning clearing, configuration, uptime, visits, inbox zero or streaks. Discovery celebration must remain optional and free of guilt.

## 10. Memory is core and newly durable

Memory is continuity: things I intentionally kept, things I need to return to, durable things about me, and enough history to re-orient myself.

Core Memory is Kept · Later · Records · History · Find. Models, external providers and semantic enrichment can all be off; the owner must still open Memory, browse and maintain its records, use Later and perform deterministic local text search. "Local baseline" means the self-hosted Worlds baseline, not an unsupported promise of browser-offline operation.

The old Worlds database does not need migration. That does not make newly created Memory disposable. Persist it outside ephemeral containers, verify restart/restore and provide a documented export/backup path. Configuration files, Memory content and execution receipts have different purposes; document their durability separately. Do not defer the baseline to the enrichment phase.

If inspection discovers active, valuable Worlds-only records that contradict the stated disposable-old-state assumption, identify them precisely before destructive retirement. Do not build speculative migration machinery otherwise.

Pollen, rylee_lore, Project Home context, semantic recall, associations and retrieval systems are optional enrichment. External systems keep authority over their own records. Preserve provenance and distinguish deliberate keeps from external references and enrichment suggestions. Automatic enrichment must not silently overwrite durable personal truth.

The journal gate remains: agents receive deliberately narrow governed answers, never arbitrary access to private text. Search results, previews, logs, receipts and caches must honor the same privacy boundary. Do not make global search or a generic Memory tool an escape hatch. Sensitive Records retain appropriate step-up.

## 11. Security and accessibility floors

Preserve OIDC, one allow-listed human owner, scoped/revocable agent tokens, server-side secret injection, references instead of embedded credentials, response/log redaction, step-up, receipts and fail-closed defaults. Verify issuer/audience and stable owner identity; do not accidentally admit every identity from the OIDC provider. Removing roles does not remove authorization checks. Keep browser session and CSRF protection appropriate to the authentication design.

Confine requests to registered destinations and path prefixes. Test URL joining, absolute URLs, path escape, resolved addresses and redirect behavior. LAN access is an explicit per-provider exception, not a global SSRF disable switch; metadata/link-local destinations retain specific protection. Refuse redirects by default and enforce bounded time, response sizes and work. Never forward Worlds credentials to a provider. Browser responses and errors never contain secret values or unrestricted upstream payloads.

Use the adopted accessibility contract across Core and Station: dark/warm default, soft but sufficient contrast, body text around 16px, labels at least 13px, visible focus, at least 44px interactive targets, stable reading order, useful accessible names, non-colour states, reduced motion and no surprise movement.

Quiet means lower emphasis, not lower legibility.

Phone and desktop are both first-class. Verify roughly 390px and 1280px, narrower/reflow conditions and zoom. No page-level horizontal overflow. Cover keyboard paths, dialogs, focus restoration, disclosure controls, errors and touch interaction. Existing lab axe results are design evidence, not verification of the new application.

Automated axe checks are required alongside manual keyboard and screen-reader walkthroughs. If manual screen-reader verification is unavailable, record UNKNOWN / outstanding, prepare the walkthrough, continue independent work and do not declare the presentation/cutover gate passed.

## 12. Build through real vertical slices

Slices and exit evidence: Approval/preservation (current proposal reconciled; ADR-0008 and supersession notes; verified remote archive; private reconstruction references). Foundation (clean backend/shell; config round-trip; reference provider through card/board; identity and confinement; action safety before writes). First service (Project Home reads, projects, Needs you, continuity and real phone/desktop presentation). Second service (Sonarr authentication, queue/list/progress, last-good behavior and useful governed actions where authorized). Third service (Homelab Health aggregation, partial failures and independent source recovery). Product completion (durable deterministic Memory; Home/Connect/Memory/Settings; comfort controls and pack invariance). Simplification (superseded code/tests/docs removed; useful properties retested in the new architecture). Production (clean install, acceptance, deploy/cutover verification and bounded rollback/retirement).

For each integration: connect → real request → map meaning → useful presentation → failures → useful authorized actions → phone/desktop → security/accessibility → coherent commit. If a later service exposes a bad abstraction, change it rather than building a contorted adapter.

After these three, inventory actual available services. For each, identify authority, human value, read/action scope, Home relevance, enrichment relevance and whether it belongs only in Connect. Add worthwhile integrations in a bounded, evidence-based order. An inventory is not a commitment to connect every API. Keep GitHub from prematurely shaping the substrate.

The reference provider must work without my estate or private tokens. Exercise list/object reads, a controlled side effect, timeout, 500, malformed response, secret injection/redaction, stale cache, redirect refusal, oversize response and lost result after dispatch.

## 13. Honest failure and verification

Track source availability, data freshness and action outcomes distinctly. A source can be unavailable while its last-good data remains useful. Show values as last-known with their timestamp; never present them as current. Missing is not zero, an empty list is not an outage, and UNKNOWN is not FAILED. No endless spinners. One failing provider never blanks Home.

Deliberately exercise healthy, empty, stale, unavailable, timeout, malformed, authorization failure and partial-data states. Test cache expiry, recovery and bounded execution. Protect sensitive caches and redact error evidence.

Run repository-required checks appropriate to each slice and the integrated release: backend/framework, UI typing/lint/build/unit/browser/axe, token/kit generation consistency, public safety and container checks. Supersede tests only when their obsolete contract is explicitly superseded; retain tests of security, privacy, authority and accessibility. Never turn a failing gate green merely by disabling it.

Keep meaningful evidence: commands, outcomes, commit/image identity, screenshots, real integration observations, failure probes and UNKNOWNs. Synthetic tests prove repeatability; real service checks prove actual wiring. Neither substitutes for the other. Rehearse dangerous write behavior against the reference provider; real destructive writes require specific authorization.

## 14. Cutover and retirement

Before cutover, prove: OIDC owner login; scoped agent access; denial, step-up and privacy boundaries. Reference provider and all three real integrations, including partial failure and recovery. Deterministic Memory with models/providers/enrichment off; durable saves, restart, search and backup/restore. Governed reads/writes, approval consumption, receipts, concurrent dispatch, crash/lost-response UNKNOWN and no replay. Phone/desktop, keyboard, reduced motion, manual screen-reader evidence and Core/Station invariance. Clean install from zero, restart and validated config reload with no old schema/runtime dependency.

Deploy the fresh replacement through the established workflow. Record the image digest and source commit; verify the running /healthz commit, not only CI or a local build. Reconnect providers through private configuration. Verify Memory persists across deployment.

Prepare the ingress switch and rollback procedure before switching. Rollback must preserve any newly created Memory, receipts and configuration; it must not replay actions. Route to the new runtime, then verify externally: OIDC, Home, real providers, governed behavior, phone and logs without secrets.

Keep the old runtime stopped or otherwise isolated during a bounded observation window. It must not keep running automation or writes alongside the replacement. Choose and document a concrete observation window and retirement criteria before cutover. If verification fails, restore routing without destroying the new durable data and record the failure.

Retire only inventoried old Worlds resources after successful observation. Do not remove shared volumes or external state. Inspect valuable Worlds-only state before deleting old data; raise any genuine contradiction. Keep the archive tag, exact deployment references and sanitized reconstruction instructions. No indefinite old/new compatibility layer unless a real consumer is discovered.

## 15. Documentation, progress and completion

Update ADR-0008, architecture, product language, PLAN, AGENTS, CURRENT, design authority and dated supersession notes so they tell one current story. Preserve append-only decision history. Old Bridge/Overview, structural Station, core Chat and legacy room/capability meanings must not remain competing instructions.

Work continuously and use coherent commits as checkpoints. Brief progress notes should state completed/changed/deleted work, real services working, gates, UNKNOWNs and next slice. When blocked, state the missing evidence or authorization and continue independent work. Do not ask whether to continue after each milestone.

Final ledger: architecture; real services; removed systems; security; Memory; governed actions; responsive UI; accessibility; production commit/image; archive; rollback/retirement; deferred work; remaining UNKNOWNs. State explicitly whether production was actually replaced and whether the old runtime remains or was removed.

Build a Worlds I can understand again later. Prefer coherence, simplicity, human meaning, real-service usefulness, replaceability, accessibility, explicit authority and honest uncertainty.

And when old Worlds no longer serves a purpose: let it go.

===== END HANDOFF =====

## Owner answers (2026-10-01)

1. Workers: workstation offload CLI, run by a foreman session.
2. Network: build here and verify against the reference provider; real services and cutover run via the workstation foreman.
3. Branching: integration branch `rebuild/front-door`.
4. Merging: the orchestrator may merge everything once checks are green.
5. Homelab Health source: the foreman inventories and proposes one.
6. Sonarr: read-only now; full governed wiring built.
7. Private config: the foreman locates it and proposes a home.
8. Project Home repo: Rylee-Bee/project-home.
9. Non-Project-Home actions: Worlds asks the owner (confirm + step-up); Worlds keeps bindings and receipts.
10. Project Home deploy gap: a separate Project Home fix PR is authorized (bind deploy approvals to the target commit, consume at dispatch, UNKNOWN outcome).
