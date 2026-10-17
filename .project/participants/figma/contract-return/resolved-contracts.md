# Resolved Play-Nice Contracts — Personal World × Figma

> **Superseded in part by [ADR-0008](../../../../docs/adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../../../FRONTEND-INVENTORY.md).

**Bundle receipt:** `nectar-heather-heather`  
**Bundle sha256:** `c3262305dc1f84f3d3c2380fadedea750ab34a61c0978c501f95f9012228a1a1`  
**Library:** rylee-bee-labs/play-nice-contracts @ `2bb60b4ab1765660d8565ae80f9b489adf91a286` (v0.3.0)  
**Adoption manifest:** `.project/contracts/adoption.yaml` (revision-pinned)  
**Resolution:** 15 of 62 contracts — chosen by the resolver for a design participant completing her contract gate (`--tag design --tag ui`), not hand-picked.

This is the canonical text of every contract in Figma's resolved bundle. Each entry carries its exact id, version, receipt, and sha256 so she can verify what she read (receipt = proof the exact file was accessible; the three-word receipt is not a credential). After reading, she attests the bundle and activates her own commitment with `contractctl commit` — or the equivalent attestation in her own words, using these exact bundle identifiers.

## Bundle contents

| # | Contract | Version | Layer | Receipt | sha256 (first 12) | Selected because |
|---|---|---|---|---|---|---|
| 1 | `ask-for-help` — Ask for Help | 1.0.0 | core | `vellum-harbor-quill` | `24fb30eca1b6…` | always |
| 2 | `design-source-and-fidelity` — Design Source and Fidelity | 1.0.0 | experience | `heather-ledger-juniper` | `328b38134433…` | library-trigger:figma |
| 3 | `explicit-state` — Explicit State | 1.0.0 | core | `driftwood-thicket-jetty` | `d3520caaba16…` | always |
| 4 | `human-reliability` — Human Reliability | 1.0.0 | human | `dell-maple-anchor` | `854e5165520f…` | always |
| 5 | `low-vision-and-reflow` — Low Vision and Reflow | 1.0.0 | human | `dell-echo-quay` | `2fbd6a44ba04…` | trigger:ui |
| 6 | `migraine-and-sensory-safety` — Migraine and Sensory Safety | 1.0.0 | human | `fathom-opal-zenith` | `aec5a96e8fed…` | trigger:ui |
| 7 | `motion-and-feedback` — Motion and Feedback | 1.0.0 | experience | `gable-fern-velvet` | `ec40b904e085…` | trigger:ui |
| 8 | `provenance-and-audit` — Provenance and Audit | 1.0.0 | core | `window-prairie-gatehouse` | `c9bfec4b0102…` | always |
| 9 | `recovery-and-reversibility` — Recovery and Reversibility | 1.0.0 | core | `meadow-fathom-aster` | `d0e07dd26de3…` | always |
| 10 | `secrets` — Secrets | 1.0.0 | security | `prairie-latch-gatehouse` | `24bd70bc7745…` | library-trigger:ci |
| 11 | `stable-truth-replaceable-machinery` — Stable Truth, Replaceable Machinery | 1.0.0 | core | `quiet-bramble-fable` | `bf5964edbc90…` | always |
| 12 | `themes-and-personalization` — Themes and Personalization | 1.0.0 | experience | `cinder-opal-window` | `74d0a5bad6fd…` | trigger:ui |
| 13 | `truth-and-evidence` — Truth and Evidence | 1.0.0 | core | `wren-loam-sail` | `634cf3e11234…` | always |
| 14 | `visual-fidelity-and-composition` — Visual Fidelity and Composition | 1.0.0 | experience | `vellum-fen-cedar` | `c915c7d64384…` | trigger:design |
| 15 | `web-ui` — Web UI | 1.0.0 | interfaces | `thicket-willow-rill` | `f9f51dc0e302…` | trigger:ui |

---

---
contract_id: ask-for-help
title: Ask for Help
version: 1.0.0
status: canonical
layer: core
applies: [humans, agents, apis, services, tools, automation, integrations, workflows]
triggers: [uncertainty, ambiguity, blocked-work, integration-work, always-applicable]
rationale: It is nice, polite, kind, and smart to ask for help. When uncertainty can be resolved more safely, cheaply, or accurately by asking another participant, asking is preferable to guessing — and knowing how to ask is what makes a system easy to integrate with.
---

<!-- contract-receipt: vellum-harbor-quill -->

# Ask for Help

## Purpose

Make asking a first-class capability across the ecosystem: humans, agents, orchestrators, workers, APIs, services, tools, and automation should be able to stop, formulate a clear question, and ask the participant who naturally owns the answer — instead of guessing merely because they are capable of generating an answer.

## NORMATIVE RULES

### Founding rule

1. When uncertainty can be resolved more safely, cheaply, or accurately by asking another participant, asking is preferable to guessing.
2. But asking must not become laziness. Do not bother another participant with work you can reliably and cheaply determine yourself. The decision ladder:
   ```text
   KNOW                        → act
   CAN SAFELY DISCOVER         → discover
   ANOTHER PARTICIPANT CAN
   ANSWER CHEAPLY              → ask
   HIGH-COST / HIGH-RISK /
   AMBIGUOUS                   → ask or escalate
   UNKNOWN AND NOBODY CAN
   ANSWER                      → preserve UNKNOWN
   ```

### Ask, don't guess

3. A participant MUST NOT invent: credentials, identifiers, ownership, authorization, user intent, destructive-action scope, unsupported API semantics, missing configuration, unknown state, provider-specific behavior, ambiguous resource selection, or requirements that materially affect the outcome — when the missing fact can reasonably be obtained from the user, another agent, a service API, capability discovery, configuration, or another authoritative system.

### Discover before asking

4. Before asking, use this order:
   ```text
   1. Inspect current known state.
   2. Consult the applicable contracts.
   3. Use safe deterministic discovery.
   4. Ask the most appropriate participant.
   5. Preserve UNKNOWN if still unresolved.
   ```
5. Do not ask a human for information already available through an authorized, inexpensive API call. Do not hammer an API when the human can answer a one-time intent question instantly. Use judgment.

### Ask the right participant

6. Route questions to whoever is best positioned to answer:
   - **Human**: intent, preference, approval, acceptable risk, product judgment, ambiguous ownership, decisions only that person can make.
   - **Service/API**: capability support, API version, current resource state, feature availability, limits, supported mutation semantics, schemas.
   - **Another agent/tool**: specialist analysis, browser inspection, image understanding, repository knowledge, platform-specific expertise, narrow reasoning better handled elsewhere.
   - **Configuration/repository/runtime**: ask the system itself before asking anyone else when the answer is already encoded there.
7. In orchestration, workers do not silently escalate scope or interrupt the human directly when blocked. A worker returns `WORKER STATE: NEEDS_HELP` with a structured question; the foreman decides whether to answer from known state, query another tool or service, ask a specialist agent, or ask the human. The foreman reduces interruption noise (see Orchestration).

### Human + machine readable questions

8. Every help request has BOTH a useful human representation and a stable machine-readable representation (see Human and Machine Parity). Do not make humans interpret raw RPC errors; do not make bots parse conversational prose when structured information is available. One fact, two representations.

### Question quality

9. A good question answers:
   ```text
   WHAT do you need?
   WHY are you asking?
   WHAT have you already checked?
   WHO is best able to answer?
   IS this blocking?
   WHAT happens if nobody answers?
   WHAT do you recommend, if appropriate?
   ```
10. Questions are concise, specific, answerable, respectful, contextual, free of unnecessary jargon, and structured for automation where possible. Lazy questions are defects:
    - Bad: "What should I do?"
    - Better: name the finding, the checked places, the options, the recommendation, and the exact decision needed.
11. Bring useful context to the interaction; the requester does the investigation legwork, not the respondent.

### Recommend without pretending

12. Where appropriate, include `recommendation`, `recommendation_reason`, and `confidence` — and clearly distinguish FACT, INFERENCE, RECOMMENDATION, and QUESTION. A recommendation is not the answer.

### Cheap to answer

13. Reduce cognitive burden: prefer a one-line decision between labeled options ("A — existing API / B — new webhook / Recommended: A") over a narrative the respondent must reconstruct. Humans get one clear decision at a time; machines get schemas and stable identifiers.

### Questions are resumable state

14. A question is workflow state, not a chat message. Record: `question_id`, `requester`, `target`, `created_at`, `reason`, `question`, `evidence`, `blocking`, `status`, `answer`, `answered_by`, `answered_at`, `resulting_action`. States: `OPEN`, `WAITING`, `ANSWERED`, `DECLINED`, `EXPIRED`, `SUPERSEDED`, `CANCELLED`. A question survives session restart, agent replacement, human interruption, and worker handoff (see Interruption and Resumption).

### Answers become provenance

15. When an answer changes what happens next, preserve the connection: `decision: {question_id, answer, answered_by, applied_to}`. Future maintainers should be able to answer "why did the system choose this?" with "because it asked, and this was the answer" (see Provenance and Audit).

### Human interruption budget

16. Attention is finite. Before interrupting a human, ask: can I answer this myself safely? can another machine answer cheaply? does the human uniquely own this decision? Batch compatible non-urgent questions where useful; do NOT batch unrelated high-consequence decisions into a confusing questionnaire (see Attention and Focus, Quiet When Healthy).

### Service-to-service help

17. Integrations ask other systems rather than hard-coding assumptions: what capabilities do you support; which API version do you speak; can you perform X; what scopes are required; do you support idempotency keys; what resource does this identifier refer to; what limits currently apply. This complements Friendly API Client, Discovery and Negotiation, Versioning and Compatibility, and Capability First.

### Capability gaps → delegate, don't duplicate

18. If system A cannot perform an operation but system B can, do not immediately recreate B inside A:
    ```text
    INTENT
      ↓
    LOCAL CAPABILITY? yes → perform
      ↓ no
    KNOWN FRIENDLY PROVIDER? yes → ask/delegate
      ↓ no
    report unsupported honestly
    ```
    Stable capability, replaceable machinery (see Capability First).

### Delegation does not remove responsibility

19. The requester still verifies the response where appropriate, preserves provenance, integrates it correctly, and reports unresolved uncertainty. "Another bot said so" is not final truth (see Truth and Evidence).

### Asking is a successful stop state

20. A task may legitimately end `STATUS: WAITING_FOR_HELP` when: further action would require guessing; the missing answer is consequential; the correct participant has been asked; current state is safely preserved. This is preferable to manufactured progress (see Bounded Work, Human Reliability).

### Questions are not authorization

21. A help response provides information, not permission. "Which cluster contains service X?" → "prod-west" does NOT imply "you may now delete prod-west." Authorization remains governed independently (see Authorization).

### Safety / privacy

22. Help requests carry no unnecessary secrets, credentials, private data, or sensitive payloads (see Secrets, Data Classification). Ask the minimum necessary question; if another participant needs sensitive data, use the appropriate secure mechanism — never paste it into general agent context.

## RATIONALE

The most expensive integration failures come from the gap between "I understand most of this" and "one thing is missing": participants guess because they can generate an answer, and something breaks. The fix is not more foreknowledge ("system A must know everything about system B") but better boundaries ("system A knows how to communicate with system B"): a system that can formulate a good question is easier to integrate, a system that can answer one is easier to use, and an ecosystem where both happen gets easier to extend every time a new participant joins. Know when you know; discover when discovery is cheap; ask when someone else naturally owns the answer; preserve uncertainty when nobody knows; never guess merely to keep moving.

## HUMAN EXAMPLES

Good interaction:

```text
Agent: I can create the deployment, but the target service exposes two supported
health-check types and this repository does not specify which one is canonical.
I checked: deployment config, service API docs, project contracts. Both are valid.
The provider recommends HTTP for web services; this service exposes /healthz.
Recommendation: HTTP /healthz. Can I use that?
Human: Yes.
Agent: Thank you. I'll use HTTP /healthz and record that decision in the
deployment configuration and provenance.
```

Bad interactions (both are defects): "I wasn't sure, so I picked TCP." (guesses) and "Please tell me how health checks work." (offloads work).

## MACHINE / IMPLEMENTATION IMPLICATIONS

- Standard artifacts: `play-nice/question-v1` (human-facing question with choices/recommendation/blocking), `play-nice/help-request-v1` and `play-nice/help-response-v1` (agent-to-agent), validated by `schema/question.schema.json`.
- Questions persist as workflow state with lifecycle states and answer provenance.
- `WORKER STATE: NEEDS_HELP` is a representable stop state in worker reports.
- Help requests are classified and secret-free by construction.
- Contract gate integration: when this contract applies, the task-impact acknowledgement identifies potential uncertainty points, available helpers, human-owned decisions, service-owned questions, and the safe stop state.

## GOOD EXAMPLES

Machine form:

```json
{"schema": "play-nice/question-v1", "question_id": "q-01842",
 "status": "WAITING",
 "requester": {"type": "agent", "id": "frontend-worker"},
 "target": {"type": "human", "role": "owner"},
 "reason": "Two approved visual references disagree about navigation placement.",
 "question": "Which navigation composition should govern the Settings screen?",
 "choices": [{"id": "rail", "label": "Left rail"}, {"id": "top-nav", "label": "Top navigation"}],
 "recommended": "rail",
 "recommendation_reason": "It matches the newer approved desktop frame.",
 "blocking": true, "safe_to_continue_without_answer": false,
 "affected_scope": ["SettingsScreen"],
 "evidence": ["design/screens/settings-desktop.png", "design/archive/settings-top-nav.png"]}
```

Human rendering:

```text
I found two approved-looking Settings designs that disagree about navigation.
The newer desktop reference uses the left rail, so that's my recommendation.
Which should I use?
[Use left rail — recommended]  [Use top navigation]
I won't change Settings until this is resolved.
```

## ANTI-PATTERNS

- "I wasn't sure, so I picked X." — guessing as progress.
- "What should I do?" — lazy question with no context.
- Ten ping interruptions for decisions a config file or API answers.
- Batching "approve prod deletion + pick a font" into one questionnaire.
- Treating an answer as permission.
- Secrets pasted into a help request "so they can test".
- A question that dies with the session (no persisted state, no provenance).
- Workers silently escalating scope, or every worker interrupting the human directly.
- Delegating and reporting "another bot said so" as verified truth.

## ACCEPTANCE CHECKS

- Did the participant check discoverable places before asking?
- Does each question answer the quality contract (what/why/checked-where/blocking/if-unanswered/recommendation)?
- Is it routed to the participant who naturally owns the answer?
- Is it cheap to answer (one decision at a time, structured for machines)?
- Is it persisted state with provenance (not scrollback)?
- Was WAITING_FOR_HELP accepted as a legitimate, safe stop state?
- Is the answer recorded as decision provenance, and never conflated with authorization?

---

---
contract_id: design-source-and-fidelity
title: Design Source and Fidelity
version: 1.0.0
status: canonical
layer: experience
applies: [design, ui, web]
triggers: [design-work, figma, tokens, ui-work]
rationale: Design tools are replaceable machinery. Semantic tokens and repo-native artifacts are the durable design truth; tool output is derived. When implementing from a visual design source, extract truth — never guess it.
---

<!-- contract-receipt: heather-ledger-juniper -->

# Design Source and Fidelity

## Purpose

Make design decisions produce artifacts useful to designers, frontend engineers, agents, tests, and future tools — and make implementation faithful to design intent without either side becoming a dependency of the other.

## NORMATIVE RULES

1. Canonical design truth lives in repo-native, portable formats: semantic tokens (`design/tokens.json`-class files), documented contracts, and implemented reference behavior. Never in a `.fig` file, a Figma project ID, a tool's internal variable store, or any vendor's API shape.
2. Tokens are semantic, not tool-internal:
   ```text
   surface.canvas  text.primary  status.needs_attention  focus.ring
   ```
   — not `Figma Variable 3348`. Generated tool representations (Figma variables, CSS custom properties) are derived artifacts, drift-checkable against the source.
3. Accessibility semantics (motion, contrast, text scale, density, targets) are core-owned. A design tool implements them; it does not own them.
4. When a visual design source (e.g. Figma) is the approved source of truth for a design stage:
   - inspect it; extract values (tokens, geometry, type) rather than guessing or eyeballing;
   - preserve design provenance where useful (frame/file IDs in handoffs make changes traceable);
   - compare implementation against the actual composition, honoring hierarchy and intent — not merely copying colors.
5. Accessibility outranks literal pixel matching. The accessibility floor is never negotiable for fidelity; when design and floor conflict, the floor wins and the conflict is recorded back to design.
6. A contributor must be able to clone the repo, inspect design contracts and tokens, and implement or redesign without any design tool.
7. Design handoffs name one authoritative source per decision; summaries route, they do not govern.

## RATIONALE

The "invented pastels" class of bug — themes that drifted because someone eyeballed a color instead of extracting it — and the "can't modify the UI without a Figma workspace" class of lock-in both come from the same root: design truth living in the wrong place. Tokens-as-contract fixes both and lets agents and tests verify fidelity mechanically.

## HUMAN EXAMPLES

- An engineer opens `design/tokens.json`, finds `status.needs_attention`, and knows its color, contrast band, and meaning — no Figma account required.
- A theme regression test fails when a hand-edited color diverges from tokens.
- A designer's frame ID lives beside the implemented component for traceability, while the component itself depends only on tokens.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- A generation step (`tokens.json` → derived CSS/tool representation) plus a `--check` drift gate in CI.
- No color literals outside the token-derived layer (enforceable by lint/test).
- Handoff documents cite frame/file IDs for provenance without making them load-bearing.

## GOOD EXAMPLES

```text
design/tokens.json (canonical, semantic)
  → gen → tokens.css (only file where hex may appear)
  → gen → Figma variables (derived, replaceable)
```

## ANTI-PATTERNS

- Hard-coded hex values scattered through components.
- Code tokens generated FROM Figma instead of TO it.
- "Just match the screenshot" implementations without extraction.
- A design system that requires a specific tool to change a spacing value.
- Pixel-perfect clones of an inaccessible design.

## ACCEPTANCE CHECKS

- Can a new contributor implement the design with zero design-tool access?
- Does the drift gate fail on token divergence?
- Are token names semantic and stable across themes?
- Did any implementation value come from eyeballing rather than extraction? (Must be no.)

---

---
contract_id: explicit-state
title: Explicit State
version: 1.0.0
status: canonical
layer: core
applies: [ui, api, cli, agents, operations]
triggers: [status-reporting, state-modeling, always]
rationale: Nobody should have to infer operational state from the absence of errors. Explicit, distinct states make systems legible to humans, agents, scripts, and future tools at once.
---

<!-- contract-receipt: driftwood-thicket-jetty -->

# Explicit State

## Purpose

Do not make humans, agents, or scripts infer state from silence. Important state is explicit, distinct, and observable — the same vocabulary everywhere.

## NORMATIVE RULES

1. Use the shared status vocabulary (`schema/status.schema.json`): `healthy, warning, needs_attention, degraded, unavailable, not_configured, disabled, stale, unknown, working, waiting, blocked, deferred, partial, complete`.
2. Do not collapse distinct states into each other: unavailable ≠ not_configured; unknown ≠ healthy; stale ≠ current; disabled ≠ failed; working ≠ complete.
3. Absence of errors is not health. If nothing has been checked, the state is `unknown`.
4. Where several states apply at once, surface the composite honestly ("degraded, two of five providers unreachable") rather than picking a misleading average.
5. The state word is the signal; color, icon, and position are reinforcement only, never the sole carrier.
6. Human interfaces may translate the vocabulary into plain language, but the machine vocabulary remains stable beneath.
7. Long operations expose intermediate states (`working`, `waiting`, `blocked`) rather than appearing frozen or silently continuing.

## RATIONALE

Personal World's status vocabulary proved that one closed vocabulary can serve a UI, a CLI, an API, and agent tooling at once — and that honest distinctions (a vacancy is not a failure) prevent both panic and complacency. State that must be inferred gets inferred wrong at the worst time.

## HUMAN EXAMPLES

- "Not configured yet" instead of a scary red failure on a feature nobody set up.
- "Last checked 3 days ago — this may be out of date" instead of showing stale data as current.
- "Waiting on approval from Rylee" instead of a task that looks stuck with no explanation.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- One closed vocabulary module shared by all surfaces (CLI, API, UI, agent tools); none invents local synonyms.
- Provider-specific states are mapped into the vocabulary at the adapter boundary.
- Statuses carry `observed_at` and `source` so freshness is machine-checkable.
- The rank order for "worst wins" composition is defined once, in the vocabulary module.

## GOOD EXAMPLES

```json
{"status": "needs_attention", "observed_at": "2026-09-11T14:00:00Z",
 "source": "provider-probe", "detail": "certificate expires in 2 days"}
```

## ANTI-PATTERNS

- A green dot as the only health indicator.
- Treating "no data yet" as healthy.
- One generic "error" state that erases the difference between misconfiguration, outage, and missing config.
- A spinner that stays for ten minutes with no intermediate state.
- Re-showing the last successful observation as current.

## ACCEPTANCE CHECKS

- Does every surface use the shared vocabulary?
- Can a newcomer distinguish "broken", "not set up", and "not checked" in this system?
- Is every displayed state paired with when it was observed?
- Do long operations expose progress states?

---

---
contract_id: human-reliability
title: Human Reliability
version: 1.0.0
status: canonical
layer: human
applies: [ui, agents, operations, product]
triggers: [always, human-facing-work, workflows]
rationale: Systems must remain safe, understandable, and operable when the person using them is not at maximum attention, memory, or energy. Human reliability is architecture, not polish.
---

<!-- contract-receipt: dell-maple-anchor -->

# Human Reliability

## Purpose

The system must not require heroics. It should absorb and organize complexity rather than requiring the human to continuously hold it in working memory. It must be operable by a person at less than their best.

## NORMATIVE RULES

1. Do not require the operator to: remember undocumented state, maintain perfect concentration, notice subtle visual differences, infer whether an operation succeeded, repeatedly inspect healthy systems "just in case", or reconstruct why a decision was made.
2. Operator attention is finite. Treat unnecessary cognitive load as technical debt.
3. After an interruption, a person should be able to answer — without reconstructing the project: What is true? Is anything unsafe or urgent? What changed? What needs me? What can wait? What should I do next?
4. Prefer: visible state over remembered state; safe defaults over perfect recall; explicit uncertainty over false confidence; reversible actions over fragile ones; one obvious path over several equivalent paths; automation over repetitive vigilance; natural stopping points over endless continuation.
5. The calm, simple interface must never depend on hiding important truth.
6. Agent and automation work must model healthy collaboration: pursue the objective, surface discoveries, distinguish required work from optional improvements, avoid performative busywork, respect stop conditions, and make it easy to say "done for now".
7. An agent must not imply that the human is obligated to continue merely because more work is possible. A healthy stable system is allowed to remain unchanged. "No action needed" is a valid and desirable result.

## RATIONALE

Extracted nearly verbatim from Personal World's Human Reliability Contract, which had itself been extracted from agent policy after the same rules were restated too many times. A system that only works when its operator is at their best fails precisely when it is needed most.

## HUMAN EXAMPLES

- Returning after a week away, the first screen answers "what needs me?" before anything else.
- A long task leaves a note about what it did and what remains, so nobody has to re-derive it.
- The assistant says "That's done. If you want, there's also X — but nothing needs you today."

## MACHINE / IMPLEMENTATION IMPLICATIONS

- Important context belongs in the environment (files, state, handoffs), not in conversation memory.
- Systems support resumption: session state, handoff documents, "where was I?" views.
- Agents emit final truth reports: CURRENT / CHANGED / VERIFIED / CONTRACTS / UNKNOWN / DEFERRED / NEXT.
- Stop conditions are defined before work begins.

## GOOD EXAMPLES

```text
5 unresolved → 3 → 1 → done.  (closure is visible and rewarded)
degraded → repaired → verified.
NEXT: nothing required.
```

## ANTI-PATTERNS

- Infinitely long checklists presented with equal urgency.
- A status page that requires cross-referencing five screens to know if anything is wrong.
- An agent that always finds "one more important thing".
- Interfaces that punish leaving and returning.
- Success that can only be confirmed by remembering what it looked like before.

## ACCEPTANCE CHECKS

- Can a tired person operate this correctly?
- Is anything critical dependent on someone's working memory?
- Is "no action needed" representable and respected?
- Can a returning user find "what needs me?" in under a minute?

---

---
contract_id: low-vision-and-reflow
title: Low Vision and Reflow
version: 1.0.0
status: canonical
layer: human
applies: [ui, web, design]
triggers: [ui-work, layout, typography]
rationale: People zoom, scale text, and use platform high-contrast modes. Layouts must survive all three without clipping, horizontal page scroll, or lost meaning.
---

<!-- contract-receipt: dell-echo-quay -->

# Low Vision and Reflow

## Purpose

Make interfaces survive real magnification: browser zoom, text scaling, and platform high-contrast modes — without trapping content, clipping controls, or forcing horizontal page scrolling.

## NORMATIVE RULES

1. Web UIs must reflow at 200% zoom (and equivalent text scaling) without clipping, truncation, or page-level horizontal scrolling. For suitable web UIs this is a release gate, verified in a real browser — not only by CSS proxies.
2. Text scaling is supported independently of zoom (preference or platform text size), with a documented floor (e.g. effective body ≥14px at scale 1.0) and a generous ceiling (≥200%).
3. Whole-page horizontal scrolling is avoided for normal application content. Dense technical tables may have contained, localized scrolling inside labeled regions — never as page-level scroll.
4. Contrast modes are coherent, not blinding: high-contrast modes increase luminance separation and add explicit component borders; they do not merely maximize brightness everywhere. Contrast targets live in a band (e.g. 8–10:1 preferred), not just a floor.
5. Component boundaries are clear on request: focus indicators, borders, and panel separation exist for people who need spatial structure.
6. Ambiguous icons have labels (text or accessible name); meaning is never positional only ("the leftmost tab is the dangerous one" is a defect).
7. Controls remain large enough (≥44px floor; larger via preference), line lengths stay readable (measure bounded), and text wraps rather than clipping (`overflow-wrap` rather than truncation for meaningful strings).
8. Platform forced-colors / high-contrast mode is supported: system palettes are not fought; app treatments are additive.

## RATIONALE

Zoom and text scaling are the most-used accessibility features in the world and the cheapest to support when designed in. Retrofitting reflow after a fixed-grid design is surgery; designing for it is a habit.

## HUMAN EXAMPLES

- At 200% zoom on a narrow window, the settings form stacks into one column; everything remains operable.
- A dense log table scrolls horizontally inside its own labeled panel; the page itself never scrolls sideways.
- With the OS high-contrast theme on, the app uses the system colors and stays fully legible.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- CI proxies: viewport-width + text-scale matrix tests; assertion of no `document.scrollingElement` horizontal overflow on app routes.
- Release gate: real-browser 200% zoom check (human or scripted real browser).
- `overflow-wrap: anywhere` for long identifiers; `text-overflow: ellipsis` only where the full value is otherwise reachable (title, detail view).
- Forced-colors media queries adjust, not override.

## GOOD EXAMPLES

```css
table.logs { overflow-x: auto; }
/* contained scrolling for a genuinely wide table, labeled by its caption */
body { overflow-x: clip; } /* never as the only reflow strategy */
```

## ANTI-PATTERNS

- Fixed-pixel layouts that clip at 150%.
- Truncated hashes with no way to see the full value.
- "High contrast" that turns the whole UI maximum-white.
- Relying on `overflow-x: hidden` to claim reflow compliance.

## ACCEPTANCE CHECKS

- Real browser at 200% zoom: every core flow operable, no page-level horizontal scroll?
- Text scale at 200%: layout survives, nothing clipped?
- Forced-colors mode: legible and coherent?
- Every truncated string reachable in full somewhere?

---

---
contract_id: migraine-and-sensory-safety
title: Migraine and Sensory Safety
version: 1.0.0
status: canonical
layer: human
applies: [ui, web, design]
triggers: [ui-work, visual-design, animation]
rationale: Interfaces should be pleasant for people sensitive to visual and motion load. These are engineering requirements, stated without any personal medical history: restrained luminance, no strobing, no required motion.
---

<!-- contract-receipt: fathom-opal-zenith -->

# Migraine and Sensory Safety

## Purpose

Design interfaces that remain usable for people sensitive to visual and motion load: low glare, restrained motion, no surprise flashes. These requirements are stated purely as engineering requirements; the medical reasons behind them belong to no repository.

## NORMATIVE RULES

1. No flashing or strobing content. No rapid luminance oscillation, ever.
2. No enormous pure-white canvases by default; no neon visual language; no required bright saturated accents. Long-session comfort is the default target.
3. Default loading indicators are static. No shimmer, no pulsing skeletons, no breathing glows.
4. No continuous decorative rotation or ambient motion by default. Peripheral movement is restrained.
5. Transitions are short and gentle (sub-300ms, ease-out class) and gated behind no-preference; motion defaults to reduced.
6. `prefers-reduced-motion: reduce` is honored unconditionally and suppresses all nonessential motion, overriding any application preference.
7. Every animated or motion-carried meaning has a static alternative. Animation never carries essential meaning.
8. Success does not require fireworks: completion feedback can be a quiet, static confirmation.
9. Where a documented relationship exists between specific hues and visual discomfort (e.g. high-glare blue range), palettes may demote those hues as a comfort decision — while never dropping below contrast minimums.

## RATIONALE

Sensory-safe design is simply good long-session design. The requirements stand on their own as engineering: nobody's visual cortex enjoys strobing skeletons at 2 AM. The personal reasons that originally motivated them are private and stay out of the library.

## HUMAN EXAMPLES

- A page that loads with a static "Loading…" indicator, not a shimmering skeleton.
- A "save succeeded" confirmation that appears quietly as text, without confetti.
- An interface that can be used for hours in a dim room without glare discomfort.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- A motion preference vocabulary with a floor of `reduced` (or stricter), where OS-level reduced-motion always overrides.
- Static fallbacks exist for every animated affordance and are the default rendering.
- CSS transitions are gated behind `prefers-reduced-motion: no-preference` in addition to application preference.
- CI-able checks: no `animation`/`transition` outside gated classes; luminance budget checks on large surfaces.

## GOOD EXAMPLES

```css
@media (prefers-reduced-motion: no-preference) {
  .card { transition: transform 160ms ease-out; }
}
/* otherwise: no transition; state changes are instant and static */
```

## ANTI-PATTERNS

- A skeleton-pulse loader as the default.
- Rotating decorative gears, bouncing mascots, or ambient breathing glows.
- Meaning revealed only by animation ("watch the arrow to see the order").
- Pure white `#FFFFFF` full-bleed background with no low-glare alternative.
- Strobing "urgent!" attention-grabbers.

## ACCEPTANCE CHECKS

- With OS reduced-motion on: is every interaction fully usable and meaningful, with zero nonessential motion?
- Is every default loading state static?
- Does any meaning depend on motion or animation?
- Could someone use this interface for three hours in a dim room comfortably?

---

---
contract_id: motion-and-feedback
title: Motion and Feedback
version: 1.0.0
status: canonical
layer: experience
applies: [ui, web, product]
triggers: [ui-work, animation, interaction-design]
rationale: Movement communicates state when it is short, purposeful, and optional — and damages usability when it is ambient, essential, or unkillable. Feedback after action is how users know the system heard them.
---

<!-- contract-receipt: gable-fern-velvet -->

# Motion and Feedback

## Purpose

Use motion sparingly as one channel of feedback among several, and make every action's result knowable without motion at all.

## NORMATIVE RULES

1. Feedback follows every consequential action: the result of a click, save, command, or request is observable — visible state change, status message, or explicit confirmation. "Nothing visibly happened" is a defect.
2. Motion defaults to reduced (or off). Nonessential animation is opt-in; OS reduced-motion overrides unconditionally (see Migraine and Sensory Safety).
3. Transitions, where allowed, are short and gentle (sub-300ms, ease-out class), never bounces, spins, shakes, or flourishes.
4. Motion never carries essential meaning: any information in an animation exists statically as well.
5. State-change feedback is honest: it reflects verified state (a "saved" indicator means saved, not "request sent").
6. Announcements are polite and rare: live-region announcements for meaningful, user-relevant changes only, batched, rate-limited; never for routine refreshes or animation states.
7. Loading states are static first (text, static progress indicators); indeterminate motion only where no progress information exists, and always with a static label.
8. Peripheral and ambient movement is restrained; nothing continuously moves on a dense surface by default.

## RATIONALE

Feedback prevents the "did it work?" re-check loop that burns attention; restrained motion protects the sensory-sensitive while still allowing a living interface for those who opt in. The static-first rule guarantees the system is fully usable with motion entirely disabled.

## HUMAN EXAMPLES

- After "Save", the button state changes, a quiet status line confirms, and the timestamp updates — no toast storm.
- A filtered list that re-renders with a 150ms fade (only for users without reduced-motion) and, for everyone, an explicit "showing 3 of 12" label.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- All transitions gated behind `prefers-reduced-motion: no-preference` AND an application motion preference at or above the chosen level.
- Status regions (`role="status"`, `aria-live="polite"`) with batched updates.
- Operation results update canonical state and are verifiable, not merely announced.

## GOOD EXAMPLES

```css
@media (prefers-reduced-motion: no-preference) {
  [data-motion="subtle"] .list-item { transition: opacity 160ms ease-out; }
}
```

## ANTI-PATTERNS

- Shimmer skeletons on every load.
- A spinner as the only loading affordance, forever, with no text.
- "Saved ✓" that fires on request dispatch, not save success.
- Bouncing attention-grabbers.
- Toasts for every routine action.

## ACCEPTANCE CHECKS

- With motion fully off: is every action's result still knowable?
- Does every consequential action produce observable feedback?
- Is any meaning carried only by motion? (Must be no.)

---

---
contract_id: provenance-and-audit
title: Provenance and Audit
version: 1.0.0
status: canonical
layer: core
applies: [data, agents, operations, security]
triggers: [state-changes, generated-content, automation, external-writes]
rationale: Meaningful state must be able to answer where it came from, what changed it, when, why, and under what policy. Without provenance, history becomes archaeology and mistakes become unexplainable.
---

<!-- contract-receipt: window-prairie-gatehouse -->

# Provenance and Audit

## Purpose

Make change explainable. Meaningful state should be able to answer, where relevant: where did this come from? who or what changed it? when? why? was it generated, and by what? what policy applied? what was the previous state?

## NORMATIVE RULES

1. Consequential changes record: actor (human, agent, service, automation), timestamp, reason or intent, and the change itself.
2. Generated content is labeled as generated, with provider, model/tool, and source material where relevant.
3. Previous state remains recoverable — through history, journal, or version control — for meaningful data.
4. Automated changes are attributable to the automation that made them, never to an anonymous "system".
5. Provenance must not force itself into the default human view. Keep it reachable (a provenance drawer, an audit endpoint), not loud.
6. Provenance records are append-friendly: corrections supersede, they do not silently rewrite history.
7. Sensitive values never appear in provenance records; references to secrets are symbolic.

## RATIONALE

"Why is this like this?" is the most expensive recurring question in a system maintained across time, interruption, and many hands. Durable provenance converts that question from archaeology into a lookup. It also makes agent work reviewable: attribution separates what an agent proposed from what the owner accepted.

## HUMAN EXAMPLES

- A journal entry changes; a small provenance note can answer: changed by Rylee, on the 4th, to fix a date, previous value recorded.
- An AI drafted a summary; it is visibly labeled "generated by <model> from <sources> on <date>".
- A service restarted overnight; the morning view can answer: which automation, why, with what result.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- Journals and audit logs are append-only, timestamped, and attributable.
- Events carry `kind` classifications (e.g. observation, mutation, approval, failure) and a provenance block (`source`, `observed_at`, `provider`, `authority`).
- Export formats include provenance fields; importers preserve them.
- Provenance is excluded from no surface entirely: every mutation path records it, even minimal ones.

## GOOD EXAMPLES

```json
{"ts": "2026-09-11T14:03:00Z", "kind": "mutation",
 "summary": "connection gitea base_url updated",
 "provenance": {"source": "cli", "actor": "rylee", "authority": "user",
                "observed_at": "2026-09-11T14:03:00Z", "provider": null},
 "previous": "http://old-host:3000"}
```

## ANTI-PATTERNS

- Silent overnight changes with no record of what or why.
- "Last updated" timestamps with no actor or reason.
- Generated content indistinguishable from human-authored content.
- Editing history in place, destroying the record of what changed.
- Provenance logs containing tokens or secret values.

## ACCEPTANCE CHECKS

- Can the next maintainer answer "who changed this, when, and why?" without reading transcripts?
- Is generated content labeled as such?
- Are automation actions attributable to a named automation?
- Is previous state recoverable for meaningful data?

---

---
contract_id: recovery-and-reversibility
title: Recovery and Reversibility
version: 1.0.0
status: canonical
layer: core
applies: [operations, agents, infrastructure, data]
triggers: [mutations, destructive-actions, deployment, automation, risky-change]
rationale: Systems fail and people make mistakes. Design recovery before relying on perfect operation; a system is only trustworthy when its failures are survivable and its mistakes are reversible.
---

<!-- contract-receipt: meadow-fathom-aster -->

# Recovery and Reversibility

## Purpose

Make mistakes survivable and failure recoverable. Recovery must not require heroics from a person who is tired, interrupted, or new.

## NORMATIVE RULES

1. Mutating operations provide, where practical, some combination of: preview or dry-run, bounded blast radius, a known-good state to return to, post-change verification, and documented rollback.
2. Backups and rollback paths exist before they are needed, and are tested, not assumed.
3. Never rely on the operator never making mistakes. Guardrails over vigilance.
4. Mistakes are evidence. Record them and improve the guardrail; do not hide them or shame the person.
5. After any mutation, verify against the authoritative source before declaring success.
6. Ambiguous state is preserved, never guessed at or deleted.
7. The recovery path itself must be documented and reachable by a newcomer, not institutional knowledge.

## RATIONALE

The homelab's hard-won rule — PROVE STALE → CLEAN, never LOOKS STALE → DELETE — exists because deletion based on an assumption destroyed real work. Reversibility is what makes bold automation safe: a system that can undo its mistakes can be allowed to try.

## HUMAN EXAMPLES

- A settings change shows a diff before saving and offers "revert to previous" after.
- Deleting a worktree first lists dirty state, unique commits, and remote backup — and refuses if any is ambiguous.
- A failed deploy restores the previous version automatically or says clearly how to.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- Destructive operations require a proof-of-staleness or safety check; the burden of proof is on deletion.
- Snapshots/checkpoints are cheap, automatic where possible, and named for the change that created them.
- Rollback is an explicit, testable path (documented command or API), not a theoretical possibility.
- `undo`/`revert`/`restore` semantics exist wherever the surface is stateful.

## GOOD EXAMPLES

```text
deploy --preview    → shows what will change, changes nothing
deploy              → applies, then verifies health; failure triggers documented rollback
```

## ANTI-PATTERNS

- "Are you sure?" as the only guardrail for a destructive action.
- Rollback documented as "restore from backup" where no tested restore procedure exists.
- Deleting anything merely because it looks unused or stale.
- Burying the undo path in tribal knowledge.
- Treating a person's mistake as a reason for shame rather than a missing guardrail.

## ACCEPTANCE CHECKS

- For each destructive action: what proof must exist before it proceeds?
- Is there a tested rollback for the most recent significant change?
- Can recovery be executed by someone who did not author the system?
- Are recent mistakes recorded with the guardrail they produced?

---

---
contract_id: secrets
title: Secrets
version: 1.0.0
status: canonical
layer: security
applies: [configuration, infrastructure, agents, api]
triggers: [always, secrets-handling, config-work, ci, agent-actions]
rationale: Secret values live only in secret stores. Everything else references them symbolically. A secret that appears in a config file, a log, a URL, a commit, or model context has already failed, wherever it was headed.
---

<!-- contract-receipt: prairie-latch-gatehouse -->

# Secrets

## Purpose

Keep secret material out of everything except secret storage: out of configs, logs, commits, exports, URLs, chat, and model context — with structural guarantees, not conventions.

## NORMATIVE RULES

1. Configuration references secrets symbolically (`token_env`, `api_key_env`, `secret_ref`) and resolves through env indirection or a secret-management boundary. Inline secret values in shareable config are rejected structurally by validation, not by review alone.
2. Never: log credentials; put secrets into normal model context or ordinary UI rendering; inline secrets into config intended for sharing; pass secrets in URLs; commit secrets to any repository.
3. Secret stores are a capability (see Capability First): native storage and external providers (Vault-class) are interchangeable adapters behind one contract; swapping the store is not surgery.
4. Exports structurally exclude secret values. Export formats reference secrets symbolically; if a future feature exports provider configuration, it exports references.
5. Sensitive vault access requires step-up authorization (see Authorization); secret values render only inside explicitly authorized secure workflows.
6. Validators reject keys that look like inline secret material (common key prefixes with value shapes like long hex/base64), with a visible, marked exception mechanism for deliberate synthetic test canaries.
7. Exposure is treated as compromise: revoke and rotate immediately with the issuer, then investigate use; history rewrites are remediation of last resort and never recall existing clones.
8. Automated gates run everywhere: CI scans every tracked text file for credential shapes and reports findings redacted (the gate never prints the value it caught).

## RATIONALE

Every real credential incident in this ecosystem came from a convenience shortcut: a token pasted into a config, a URL that carried it, a client bundle that inlined it. Structural exclusion (validator-rejected key shapes, export whitelists, indirection-only config) is what survives tired humans and hurried agents — conventions do not.

## HUMAN EXAMPLES

- A connection config says `token_env: GITEA_TOKEN` — and a test proves no file in the repo contains a plausible token value.
- Rotation is a documented operation: change the value in the store; nothing else moves.
- An agent asked to "fix the auth issue" is structurally unable to read the token even while debugging it.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- Secret resolution is a boundary (env/secret manager); consumers never see source material except the resolved value in-process.
- Public-safety CI gate: shape-scanning with redacted reporting and a marked synthetic-canary exception (e.g. `pn-safety: synthetic`).
- Export validators: structurally unable to include secret-classified fields.
- No secret value ever enters prompts, tool arguments, or logs — enforce at the boundary, log the reference instead.

## GOOD EXAMPLES

```json
{"type": "gitea", "capability": "source_control",
 "token_env": "GITEA_TOKEN", "required": false}
```

## ANTI-PATTERNS

- `{"api_key": "sk-EXAMPLE-..."}` in a tracked config (any realistic credential shape belongs nowhere; use reserved example values such as `sk-live-EXAMPLE` only in deliberate, marker-carrying canaries).
- Tokens in remote URLs (rewrite + rotate on discovery).
- "Just paste it here so I can test" in an agent session.
- Logs that dump request headers.
- An ignore rule trusted to protect an already-tracked file.

## ACCEPTANCE CHECKS

- Does the shape-scanning gate pass on the whole tree?
- Can any export produce a secret value? (Must be structurally impossible.)
- Are all secrets resolvable-but-invisible to agents and logs?
- Is rotation documented and does anything break when it happens? (List what.)

---

---
contract_id: stable-truth-replaceable-machinery
title: Stable Truth, Replaceable Machinery
version: 1.0.0
status: canonical
layer: core
applies: [architecture, data, agents, design, infrastructure]
triggers: [new-dependency, storage-decision, index, cache, tooling, migration]
rationale: Every tool is temporary; the truth it manages must not be. Canonical truth lives in durable, inspectable formats that survive the replacement of any model, service, index, or framework.
---

<!-- contract-receipt: quiet-bramble-fable -->

# Stable Truth, Replaceable Machinery

## Purpose

Ensure that replacing any piece of machinery — AI model, agent harness, database, vector store, index, embedding model, API gateway, source-control host, deployment tool, monitoring platform, design tool, UI framework, automation framework — never destroys the truth it was managing.

## NORMATIVE RULES

1. Canonical truth lives in durable, inspectable formats (plain files, Git, append-only journals, explicit schemas) wherever practical.
2. Anything derivable is derived, not canonical: indexes, vector stores, semantic caches, compiled artifacts, and generated files must be rebuildable from canonical sources, and a rebuild path must exist.
3. No tool may become the only place truth exists. If deleting a tool would erase knowledge, the architecture is wrong.
4. Machinery may accelerate, enrich, automate, or present truth. It may not own truth.
5. Swapping a provider for another must feel like changing a part, not surgery. If it feels like surgery, the boundary is wrong.
6. AI output that becomes durable truth is committed to canonical storage with provenance — not left living only inside a conversation, model, or session.

## RATIONALE

The ecosystem repeatedly rebuilt knowledge after tools changed: model migrations stranded context living in chats; index rebuilds lost data that had no canonical source. Durable, plain, inspectable truth also plays nice with humans, agents, Git, and future tools — it is the most interoperable format there is.

## HUMAN EXAMPLES

- Your journal, decisions, and contracts live in Markdown files under Git — not in a SaaS wiki or one AI assistant's memory.
- Deleting the search index is an inconvenience, not a catastrophe: everything is re-indexable from source files.
- Switching from one vector database to another costs configuration and a rebuild script, never your data.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- Every derived artifact declares its canonical source and its rebuild command.
- Exports exist for canonical data (import/export is a first-class feature, not an afterthought).
- Provider-specific data is namespaced; canonical data is provider-neutral.
- Derived artifacts are drift-checkable (`build --check`), so silent divergence is detectable.

## GOOD EXAMPLES

```text
world.json (canonical)
  ↓ reindex
search index (derived, rebuildable, never canonical)
```

## ANTI-PATTERNS

- The only copy of a design decision is a Figma comment.
- Conversation history with an AI as the sole record of what was decided.
- A vector store as the only place memories exist, with no export.
- Generated code that must be edited by hand while a generator still claims ownership.
- Canonical schema expressed as the internal shape of vendor product X.

## ACCEPTANCE CHECKS

- For each piece of machinery: what exactly survives its replacement?
- Is there a working rebuild path for every derived artifact?
- If this tool vanished today, what truth would be unrecoverable?
- Is any AI-generated truth persisted canonically with provenance?

---

---
contract_id: themes-and-personalization
title: Themes and Personalization
version: 1.0.0
status: canonical
layer: experience
applies: [ui, web, product]
triggers: [ui-work, theming, preferences]
rationale: Allow customization without destroying product coherence or accessibility. Layering keeps user comfort, themes, and decoration from fighting the floors beneath them.
---

<!-- contract-receipt: cinder-opal-window -->

# Themes and Personalization

## Purpose

Let people make the product theirs — personality, accent, density, contrast, motion, companions — without letting customization erode accessibility, coherence, or meaning.

## NORMATIVE RULES

1. Personalization is layered; a lower layer may never violate a requirement above it:
   ```text
   PLATFORM / ASSISTIVE REQUIREMENT
           ↓
   ACCESSIBILITY FLOOR
           ↓
   USER COMFORT
           ↓
   THEME / PERSONALITY
           ↓
   DECORATION
   ```
2. A theme must not break accessibility: every theme ships against the same floor, verified.
3. Comfort settings may adjust density, contrast (within floor+band), target sizing (upward), text scaling, and motion (within floor) — never below the floor.
4. Themes may affect: personality, companion presence, accent, iconography, aesthetic tone. Decoration is decoration: personality never carries operational meaning (a mascot is never a status indicator).
5. Themes are switchable and removable: turning a theme off loses no functionality. Companion art is decorative and `aria-hidden`; the actionable control keeps its own useful label.
6. Theme and comfort preferences are user-owned state: exportable, portable (see Portability), and never silently imposed on other users of the same system.
7. A coherent product remains coherent: themes alter presentation slots defined by the core; they do not reorder information architecture or invent new navigation concepts.
8. No value combination in any preference schema may violate the floor — structurally validated, not policy-promised.

## RATIONALE

Personalization that fights accessibility forces a cruel choice; personalization without layering fights itself. The layering pyramid (distilled from Personal World's accessibility contract and preference schema) lets a thousand users have a thousand comfortable, accessible experiences over one coherent product.

## HUMAN EXAMPLES

- A dark, low-glare default; a high-contrast comfort mode with added borders; both pass AA.
- A companion character that can be turned off with zero functional loss.
- Dense layout for the expert, relaxed layout for the tired evening — same product, same meaning.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- Preference schemas encode floors (`minimum` constraints) and are validated server-side; the client cannot submit floor-violating combinations.
- Theme manifests declare the slots they may fill; unknown slots are rejected.
- Accessibility semantics (motion, contrast, text scale, targets) are core-owned state or schema — themes consume, never own.
- Theme application never changes DOM semantics or source order.

## GOOD EXAMPLES

```json
{"motion": {"values": ["off", "reduced", "subtle"], "default": "reduced", "floor": "off"},
 "targets": {"values": ["standard", "large"], "default": "standard", "floor": "standard"}}
```

## ANTI-PATTERNS

- A "cute" theme that reduces contrast below AA.
- A mascot whose expression is the only signal for system health.
- Preferences that only the client enforces.
- A theme that reorders the DOM for looks, breaking screen-reader order.
- One user's theme becoming every user's default.

## ACCEPTANCE CHECKS

- Are all floor constraints validated server-side against every theme and preference combination?
- Does turning every personalization off yield a fully functional, fully accessible product?
- Does any decoration carry operational meaning? (Must be no.)

---

---
contract_id: truth-and-evidence
title: Truth and Evidence
version: 1.0.0
status: canonical
layer: core
applies: [engineering, agents, operations, testing]
triggers: [always, verification, reporting, status, claims]
rationale: Systems drift into failure when reports are trusted as reality. Make honesty cheaper than fabrication by tying claims to evidence and treating UNKNOWN as a first-class, valid state.
---

<!-- contract-receipt: wren-loam-sail -->

# Truth and Evidence

## Purpose

Make honesty cheap. Truth must be easier to discover than to fabricate, for humans and agents alike. A claim about a system's state is worth exactly the evidence behind it.

## NORMATIVE RULES

1. `UNKNOWN` is a valid state. Never silently convert it into `healthy`, `PASS`, or `complete`.
2. Running is not working. Implemented is not verified. HTTP 200 is not proof of correctness. A process being up is not evidence it does its job.
3. An agent report is evidence about what an agent said, not proof of what happened. Current evidence outranks historical reports, summaries, and remembered conclusions.
4. Every consequential claim carries its evidence: the file, log, test, command output, or live query that produces it.
5. Do not fabricate plausible detail. If a value, name, SHA, or count is not observable, report it as unknown rather than guessing.
6. Never present inferred state as observed state. Label them distinctly.
7. Verification uses the authoritative source, not a mirror, cache, or downstream copy, unless the mirror's freshness is itself verified.
8. A check that has not run in the current context is `UNKNOWN`, regardless of how green it was last time.

## RATIONALE

The single most repeated lesson across this ecosystem (Personal World, VEFR, homelab, rylee_lore): confident summaries drift from reality, and drift compounds silently until something breaks at the worst moment. Fabrication must be more expensive than observation — structurally, not morally.

## HUMAN EXAMPLES

- A dashboard that says "healthy" must have actually checked something recently, and must say `stale` or `unknown` when it hasn't.
- "The deploy went fine" is not done. "The deploy went fine; `GET /healthz` returned 200 at 14:02 and the version endpoint reports the new build" is done.
- "I don't know" from a tool should be treated as useful information, not a failure to hide.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- Status values come from the shared vocabulary (`schema/status.schema.json`); no surface invents its own.
- Statuses carry `observed_at` timestamps and `source` provenance so age is checkable.
- Verifiers prefer live queries over stored results; stored results carry their observation time.
- APIs must not return cached data marked as fresh.

## GOOD EXAMPLES

```json
{"status": "unknown", "observed_at": null, "source": "healthcheck",
 "note": "never checked; not run in this session"}
```

```json
{"status": "healthy", "observed_at": "2026-09-11T14:02:00Z",
 "source": "GET /healthz", "warnings": []}
```

## ANTI-PATTERNS

- `status: "Service seems okay :)"` — unverifiable, unparseable.
- Defaulting status fields to `healthy` before any check runs.
- Treating a CI badge from yesterday as today's truth.
- An agent asserting "all tests pass" without naming the command it ran.
- Silently substituting the last known value when a check fails.

## ACCEPTANCE CHECKS

- Can a reader distinguish observed, inferred, and unknown states in every report?
- Does every status carry a checkable source and observation time?
- Is any `healthy`/`PASS`/`complete` claim traceable to current evidence?
- Would a deliberately wrong claim be caught by the system, or only by vigilance?

---

---
contract_id: visual-fidelity-and-composition
title: Visual Fidelity and Composition
version: 1.0.0
status: canonical
layer: experience
applies: [ui, web, design, agents]
triggers: [ui-implementation, design-work, frontend, agent-ui-work]
rationale: Tokens can remain perfectly synchronized while the product still drifts dramatically from design intent. Composition — rhythm, hierarchy, grouping, density — is design truth too, and must be verified, not remembered. Anything important enough to preserve must have a deterministic gate, an explicit required human/browser gate, or both.
---

<!-- contract-receipt: vellum-fen-cedar -->

# Visual Fidelity and Composition

## Purpose

Close the gap between "the values are right" and "the design is right". A product may have perfect token fidelity and still substantially violate its design. Passing token checks MUST NOT be treated as proof of design fidelity.

Provenance note: this contract encodes a lesson first observed during a real frontend UAT (Personal World, September 2026): semantic design tokens survived implementation with mechanical verification, yet the shipped screens drifted dramatically from the intended Figma composition — screen rhythm, grouping, density, card-vs-list choices, hierarchy, whitespace, and companion placement. Token fidelity had a deterministic gate; composition fidelity had prose and human memory. Prose and memory are not gates. This contract generalizes that lesson; no project is a dependency of it.

## NORMATIVE RULES

### 1. Four kinds of design truth

2. Distinguish at all times:

   ```text
   SEMANTIC     — What does this thing mean?
   TOKEN        — What visual primitives does it use?
   COMPOSITION  — How are information, hierarchy, rhythm and space organized?
   BEHAVIOR     — How does it respond and interact?
   ```

3. Each kind has its own truth, its own verification, and its own drift. Semantic and token truth do not imply composition truth. Verification of one kind MUST NOT be reported as verification of another.

### 2. Composition is first-class design data

4. Composition includes: page structure, information hierarchy, grouping, relative prominence, whitespace, alignment, density, repetition, surface usage, card/list/table choices, visual rhythm, companion/artwork placement, navigation relationship, and responsive transformation.
5. Treat these as intentional decisions rather than incidental CSS. Composition decisions are written down — in screen specs, design references, or annotated baselines — not implied by whatever the implementation happened to produce.

### 3. Component gravity

6. Reusable component libraries create architectural and design gravity: if a generic component exists, humans and agents will reuse it even where inappropriate.
7. Shared design systems therefore define not only WHAT COMPONENT EXISTS but also WHERE IT IS APPROPRIATE and WHERE IT IS NOT. Example:

   ```text
   Card
   GOOD: standalone actionable item; discovery/feed content;
         truly bounded entity requiring separation
   BAD:  every status; every summary; every heading group;
         arbitrary page sections
   ```

8. Where misuse repeatedly causes drift, enforce usage through lint rules, wrapper APIs, tests, component ownership conventions, or architectural checks. Do not rely on prose alone when a recurring mistake can be mechanically prevented.

### 4. Design references must be easy to find

9. Every implementation surface has an obvious, current design reference, reachable by a deterministic mapping (e.g. `frontend/src/screens/TodayScreen.tsx` ← `design/screens/today.png` + `design/screens/today.md`), or another documented convention.
10. An implementer must not search several historical documents to determine which visual is current.

### 5. One current canonical pointer

11. Exactly one location answers: "What is the currently approved visual composition?" — e.g. `design/CURRENT.md`. It identifies:
    - the current approved design package;
    - its revision/date;
    - relevant screen references;
    - superseded visual packages (marked historical);
    - canonical tokens;
    - accessibility authority;
    - known intentional deviations.
12. Historical documents remain historical. Three partially-canonical documents competing is a defect: the pointer wins, and its superseded list explains why.

### 6. AI design implementation gate (hard workflow requirement)

13. For substantial user-facing UI implementation by an AI agent, BEFORE writing code:
    ```text
    1. Open the current design reference.
    2. Open the current running implementation.
    3. Compare them side by side.
    4. Record meaningful differences.
    5. Only then propose or delegate implementation.
    ```
14. The comparison covers: composition, hierarchy, density, typography, surfaces, proportions, personality, responsiveness, attention behavior. This is a hard workflow requirement, not a suggestion. "I read the design contract" without the comparison is not compliance.
15. For existing interfaces, the loop is:
    ```text
    DESIGN REFERENCE + LIVE BROWSER → DIFF/FINDINGS → IMPLEMENTATION → LIVE BROWSER → VERIFY
    ```
    Do not infer visual correctness exclusively from JSX/CSS source.
16. Where technically practical, place the reference artifact where the implementation agent is explicitly instructed to inspect it. Agent task briefs identify exact reference files:
    ```text
    Implementation:  frontend/src/screens/TodayScreen.tsx
    Visual reference: design/screens/today.png
    Behavior contract: contracts/experience/...
    Accessibility:    contracts/human/ACCESSIBILITY_FLOOR.md
    ```
    Reduce search ambiguity; a link several levels away is not sufficient.

### 7. Wrong vs right examples

17. Where a recurring design failure is known, preserve an explicit anti-pattern example: a `wrong/`/`right/` pair or a single annotated comparison board. Example:
    ```text
    WRONG: card-per-datum status dashboard
    RIGHT: heading + quiet divider + grouped list
    ```
18. Agents learn extremely effectively from concrete contrast. Do not rely only on statements such as "don't overuse cards" — show what replacing the anti-pattern actually looks like.

### 8. Visual regression

19. Where suitable: use Playwright (or equivalent), capture canonical viewport screenshots, store reviewed baselines, compare meaningful surfaces, and require intentional updates to baselines. Lightweight is fine; presence is required for surfaces with an approved composition.
20. Three verification layers, all necessary:
    ```text
    Token checks:       Did our primitives change?
    Visual regression:  Did the screen change?
    Human UAT:          Is the change actually good?
    ```
21. Visual regression does not replace human design review; it catches accidental compositional drift between accepted states.

### 9. Design verification levels

22. Encode and report design verification as levels; do not declare design verification complete because D0/D1 pass:
    ```text
    D0 — TOKENS:     colors, typography primitives, spacing values
    D1 — STRUCTURE:  correct semantic elements/components
    D2 — COMPOSITION: hierarchy, grouping, density, rhythm, proportion
    D3 — BEHAVIOR:   responsive, interactions, states
    D4 — EXPERIENCE: does the actual human experience match the intended product?
    ```
23. D2 and D4 require eyes: browser comparison and human acceptance respectively. D0 alone is never sufficient evidence of fidelity.

### 10. Visual contract attestation

24. When a task resolves this contract, its task-impact acknowledgement explicitly identifies:
    ```text
    design reference:
    live surface:
    known intended composition:
    known anti-patterns:
    verification method:
    ```
    Example:
    ```text
    VISUAL IMPACT
    reference: design/screens/today-rylee.png
    surface:   /today
    preserve:  greeting-area companion; plain grouped capability rows; quiet healthy state
    avoid:     card-per-datum; status-chip noise
    verify:    browser side-by-side; Playwright baseline; true 200% zoom
    ```
    This prevents "I read the design contract" from becoming meaningless boilerplate.

### 11. Composition must respect attention design

25. A composition is incorrect if it technically resembles a mockup but violates: quiet-when-healthy, What/Why/Next, obvious focus, progressive disclosure, interruption recovery, or complexity on demand.
26. Likewise, attention simplification must not erase the approved visual personality. Design fidelity is both visual and functional.

## RATIONALE

The observed failure mode: a token drift gate proved the primitives were synchronized while the shipped screens no longer resembled their design — because the gate measured the wrong layer. Composition drift is as real as token drift and far more insidious, since nothing red goes off when it happens. The fixes are structural: composition written down as data (specs, baselines), component misuse made mechanically preventable, one canonical pointer for what is current, a forced compare-before-code gate for AI implementers, and verification levels that name which layer was actually checked.

## HUMAN EXAMPLES

- An agent implementing TodayScreen opens `design/screens/today.png` and the live `/today` in a browser first, records "grouped list vs current card grid; companion missing from greeting area", then implements — and the PR's attestation shows the comparison happened.
- A visual-regression diff fails when a status page quietly becomes card-per-datum, before anyone internalizes the drift.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- Screen reference mappings are deterministic and documented (screen → reference files).
- `design/CURRENT.md` (or equivalent) is a data file: package id, revision, screen list, superseded list, deviations.
- Component libraries encode usage guidance alongside definitions; lint/architectural rules exist for known recurring misuses.
- Visual regression baselines are reviewed artifacts; updates to baselines are explicit, intentional commits.
- Attestation schema accepts the VISUAL IMPACT block fields (reference, surface, preserve, avoid, verify).

## GOOD EXAMPLES

```text
D-verification report for /today:
D0 TOKENS: PASS (token-drift test green)
D1 STRUCTURE: PASS (landmarks, components correct)
D2 COMPOSITION: PASS (browser side-by-side vs design/screens/today.png; diff: none)
D3 BEHAVIOR: PASS (200% zoom reflow; reduced-motion off)
D4 EXPERIENCE: PASS (human UAT, Rylee 2026-09-12)
```

## ANTI-PATTERNS

- "Tokens all green" reported as "design verified".
- Composition decisions living only in a Figma file's arrangement and one person's memory.
- A Card component used for every status, summary, and section because it exists.
- Three design docs, each partially canonical, none authoritative.
- An agent implementing from the source code's existing habits without opening the reference.
- Baseline screenshots updated reflexively to make diffs go away.

## ACCEPTANCE CHECKS

- Can an implementer find the current approved composition of any screen in one lookup?
- Did any substantial UI task record a design-reference-vs-live comparison before coding?
- Are known recurring misuses mechanically prevented (lint/wrapper/test), not just proscribed?
- Is design verification reported by level (D0–D4), with D2/D4 honest about needing eyes?
- Does the attestation's VISUAL IMPACT name real files, real surfaces, and a real verification method?

---

---
contract_id: web-ui
title: Web UI
version: 1.0.0
status: canonical
layer: interfaces
applies: [ui, web]
triggers: [ui-work, frontend]
rationale: The web UI is another view of the same system: same capabilities, same vocabulary, same truth. It renders the API's state honestly, never invents data, and never becomes the only way to operate the product.
---

<!-- contract-receipt: thicket-willow-rill -->

# Web UI

## Purpose

Make the web interface a friendly view of the same system the CLI and API expose — honest about state, accessible by default, and never a load-bearing single point of operation.

## NORMATIVE RULES

1. The UI is a view, never the source of truth: it renders API/CLI-shared state; it holds no truth of its own. Nothing on screen is fabricated — every displayed value comes from a real response field, or is explicitly labeled as unknown/loading.
2. Every concept operable in the UI is understandable and operable without it (see CLI parity). The UI may make workflows easier and more discoverable; it must never become the only way to understand or operate the system.
3. The UI renders canonical states only: the shared status vocabulary, real data, honest empty states ("No journal entries yet" — not fake data, not blank mystery), and explicit loading/error states per section (see Explicit State, Failure and Degradation).
4. A failing section degrades alone: one broken widget never blanks the page; per-section states are independent.
5. Accessibility floor applies fully (see Accessibility Floor and its sibling human contracts): keyboard, focus, targets, labels, zoom/reflow, reduced motion.
6. The UI respects the depth ladder: glanceable defaults, drill-down to technical detail, specialist hand-off links at the bottom of the hierarchy (see Complexity on Demand).
7. Presentation preferences (theme, density, motion) come from core-owned preference state/schemas — never from the theme alone (see Themes and Personalization).
8. Design truth follows the design contracts (see Design Source and Fidelity, Visual Fidelity and Composition): semantic tokens, verified composition, no hand-invented values.
9. No external network requests at runtime for assets that could be self-hosted; a deployed UI works offline in its own network.

## RATIONALE

Every system here that treated the UI as "the product" and the CLI/API as plumbing became fragile: UI rewrites became rewrites of the product, and UI-only state drifted from real state. UI-as-view proved cheaper to maintain, test, and replace — and it keeps agents, scripts, and tired humans equally first-class.

## HUMAN EXAMPLES

- The dashboard shows `not_configured` for a capability nobody wired up — an honest vacancy, styled calmly, with a "set up" action.
- A legacy HTML dashboard is deleted in one commit after parity is proven, because the API beneath never depended on it.

## MACHINE / IMPLEMENTATION IMPLICATIONS

- UI state derives from the same endpoints/schemas the CLI uses; typed clients shared.
- Component libraries render from capability manifests and status vocabulary, not hard-coded provider lists.
- Automated browser checks (axe-class, target size, reflow proxies) run in CI; real-browser gates stay human.
- Fabricated-data tests: fail on any hardcoded demo content that pretends to be real.

## GOOD EXAMPLES

```json
// API says: {"status": "not_configured"} → UI renders the word + setup action
// UI never invents {"status": "healthy"} to look complete
```

## ANTI-PATTERNS

- Demo data left in production screens.
- A UI-only status notion ("kinda broken") absent from the vocabulary.
- Operation possible only by clicking through five screens.
- One failed fetch rendering the whole app blank.
- The UI as the sole recovery path for a broken deployment.

## ACCEPTANCE CHECKS

- Does every displayed value trace to a real response field?
- Is every screen usable at the accessibility floor?
- Could the UI be deleted and rebuilt from the API without losing operability?
- Do sections fail independently?

---
