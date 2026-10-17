# Human Reliability Contract

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the human-reliability contract (safe, understandable, recoverable operation under low attention/energy) · **Read this if:** you are designing or reviewing any human-facing surface, agent behavior, or operational workflow.

**In short:** Worlds must stay safe, understandable and easy to operate when the person is tired, unfocused, or interrupted. Human reliability is an architectural requirement, not polish — this page lists the rules and acceptance questions that enforce it.

## Purpose

Worlds must remain safe, understandable, recoverable, and
easy to operate when the person using or maintaining it is not
operating at maximum attention, memory, energy, or tolerance for
complexity.

Human reliability is an architectural requirement, not polish.

The system should absorb and organize complexity rather than requiring
the human to continuously hold that complexity in working memory.

This contract complements, rather than replaces:

- the Accessibility contract (`docs/accessibility/ACCESSIBILITY_CONTRACT.md`);
- the Public Repository Boundary contract (`SECURITY.md`);
- the Provider-Neutral Baseline (`docs/NATIVE-BASELINE-AND-ENRICHMENT.md`).

Previously the authoritative text of this contract lived inside
[`AGENT_POLICY.md`](../AGENT_POLICY.md). That file still states the
policy; this file is now the canonical contract. Register it in
[`AGENT_CONTRACTS.md`](../AGENT_CONTRACTS.md).

## The Short Version

Build the appliance so it does not require heroics.

Prefer:

- visible state over remembered state;
- safe defaults over perfect recall;
- explicit uncertainty over false confidence;
- reversible actions over fragile ones;
- one obvious path over several equivalent paths;
- meaningful automation over repetitive human vigilance;
- natural stopping points over endless continuation;
- useful summaries over raw information overload;
- continuity over dependence on one person's current working memory.

A person should be able to return after an interruption and answer:

- What is true?
- Is anything unsafe or urgent?
- What changed?
- What needs me?
- What can wait?
- What should I do next?

without reconstructing the entire project.

## Humans Are Part of the System

Design assumptions must not require the operator to:

- remember undocumented state;
- maintain perfect concentration;
- notice subtle visual differences;
- infer whether an operation succeeded;
- remember every unfinished task;
- repeatedly inspect healthy systems "just in case";
- reconstruct why a decision was made;
- work through fatigue merely to leave the project safe;
- maintain maximum cognitive capacity for routine operation.

Operator attention is finite.

Treat unnecessary cognitive load as technical debt.

## Human Experience Questions

Before accepting a design, ask — from `AGENT_POLICY.md`, preserved
here as acceptance criteria:

- What does the person think is happening?
- What actually is happening?
- Can those differ silently?
- What needs attention?
- What can safely wait?
- What is healthy?
- What is unknown?
- Can the person recover without understanding implementation internals?

Keep the interface simple without hiding important information.

## Explicit State

Do not make humans infer operational state from absence of errors.

Use explicit states such as:

- `UNKNOWN`
- `NOT_CONFIGURED`
- `DEGRADED`
- `WORKING`
- `WAITING`
- `BLOCKED`
- `DEFERRED`

Evaluate applicable contracts as `PASS` / `FAIL` / `N/A` / `UNKNOWN`.

In particular:

- Unknown is not healthy.
- Not configured is not failed.
- Implemented is not verified.
- Running is not necessarily correct.
- Never silently convert `UNKNOWN` into `PASS`.

## No Manufactured Urgency

Agents and automation MUST NOT turn backlog size, remaining context,
unfinished ideas, or operator capability into artificial urgency.

The existence of more useful work does not mean more work is currently
required.

A healthy stable system is allowed to remain unchanged.

"No action needed" is a valid and desirable result.

## Bounded Work and Stop Conditions

Substantial work should have a bounded objective. Separately useful
improvements belong in `DEFERRED`, the roadmap, or an issue — not
silently absorbed into an endless work session.

Stop, preserve state, and report when:

- the requested objective is complete;
- further work has sharply diminishing value;
- a human decision is required;
- evidence is insufficient;
- two authoritative sources genuinely conflict;
- the next action would materially increase risk;
- verification cannot currently be completed.

Stopping with an explicit `WAITING`, `BLOCKED`, `UNKNOWN`, or `DEFERRED`
state is preferable to manufacturing progress.

## Closure Is Part of the Work

A substantial work session is not complete merely because code was
written. The final truth report (`CHANGED` / `VERIFIED` / `CONTRACTS` /
`ACCESSIBILITY` / `OWNERSHIP,SECURITY` / `UNKNOWN` / `DEFERRED` /
`NEXT`) exists so another human or agent can resume without
archaeological reconstruction.

`NEXT: nothing required` is a successful outcome.

## Recovery Before Heroics

When practical, mutating operations should have some combination of:

- preview or dry-run;
- bounded blast radius;
- known-good state to return to;
- post-change verification;
- documented rollback.

Prefer making recovery easier rather than relying on the operator to
never make mistakes. Mistakes should become evidence and improved
guardrails, not shame or hidden history.

## Progressive Disclosure

Human-facing surfaces should present the smallest useful amount of
information first, then permit deeper inspection.

Do not remove technical depth. Organize it.

Avoid making the operator parse walls of successful checks to discover
the one relevant failure. This requirement works together with the
Accessibility contract.

## Agent Work Should Model Healthy Collaboration

An agent should:

- pursue the requested objective;
- surface meaningful discoveries;
- distinguish required work from optional improvements;
- preserve uncertainty;
- avoid performative busywork;
- respect stop conditions;
- make it low-effort for the human to say "done for now."

An agent MUST NOT imply that the human is obligated to continue merely
because additional work is possible.

## Acceptance Questions

Before declaring substantial work complete, ask:

| Question        | Test                                                              |
| --------------- | ----------------------------------------------------------------- |
| Understandability | Can the operator determine current state without reconstructing history? |
| Attention       | Are important exceptions easier to find than routine successes?   |
| Memory          | Is anything critical dependent only on someone's working memory?  |
| Recovery        | If this change is wrong, can we recognize that and recover reasonably? |
| Truth           | Are unknown, untested, inferred, and verified states distinguished? |
| Scope           | Did the task stop at a sensible boundary?                         |
| Continuity      | Can another session resume without repeating the investigation?   |
| Human load      | Did this change make the system easier — or at least no harder — to operate when attention or energy is limited? |

If an answer is materially "no," either address it or preserve it
explicitly as unresolved work.

## The Success Condition

The goal is not to eliminate complexity. The goal is to make
complexity navigable.

A successful Worlds can support deep engineering when the
person wants depth while staying low-stimulation, safe, and understandable when
the person needs simplicity.

The operator should not have to be at their best for the system to
behave at its best.