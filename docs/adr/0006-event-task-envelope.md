# ADR-0006: One task/event envelope = the journal event shape (transport-agnostic)

> **Status:** Direction · **Verified:** 2026-09-26 · **Canonical for:** the task/event envelope direction (proposed, review-only) · **Read this if:** you are designing how Workbench tasks and Agent operations record events.

**Scope note:** proposed and review-only. `.project/PLAN.md` wins on scope and sequencing.

**In short:** proposed, not accepted. If accepted, Workbench tasks and Agent operations share one transport-agnostic event envelope that is a **journal event shape** — not a new bus or store. NATS or any durable broker is added only when a named trigger fires. A spike (2026-09-21) showed the journal accepts the extra fields additively.

- Status: **proposed** (review-only per owner D22; not yet accepted)
- Date: 2026-09-21
- Supersedes: none
- Enforced by: the journal/event contract; `tests/test_framework.py`
- Normative doc: `docs/ARCHITECTURE.md` (journal); ADR-0001

## Context

Owner direction (human, 2026-09-21): Workbench tasks and Agent operations must share **one** event/task
model. The contract must be frozen **independently of transport**, and no permanent new service (e.g. NATS)
is added merely because the future *might* need it. The existing append-only `journal.ndjson` is the
natural home.

## Decision

1. **One common, transport-agnostic event envelope:**
   `event_id · timestamp · source · subject/type · task_id · state · payload · correlation_id`.
2. **The envelope is a journal event shape** — it extends the existing append-only journal; it is **not** a
   new bus or store.
3. **First transport = authenticated WebSocket through the existing FastAPI stack.** WebSocket/HTTP framing
   stays **out** of the envelope; the durable fields are `correlation_id`, `task_id`, and `state`, so
   swapping transport never changes the contract.
4. **NATS (or any durable broker) is adopted only when a named trigger fires:** durable replay across
   restarts · offline agent queue · fanout / multi-worker. Until one is an *actual* requirement, add no new
   permanent service.
5. **Task / Build are vocabulary over the envelope.** A Task = a unit of executing work (inputs · status ·
   logs · workspace-or-node · artifacts · events). A Build = a Task with step structure. Worlds **wraps**
   the underlying executor (Task / Dagger / shell / remote Node operation); it does not build a new
   execution engine.

## Consequences

- One event model across Workbench + Agent; transport is swappable without touching the contract.
- No premature NATS; the trigger threshold is explicit, not a vibe.
- Future cost: the WebSocket-first path has no durable delivery — a task that must survive a dropped
  connection is the trigger that tips toward a durable broker.