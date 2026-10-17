# ADR-0009: Rebuild Worlds on the Play-Nice semantic kernel

**Status:** proposed  
**Date:** 2026-10-04  
**Scope:** `rebuild/front-door`

## Decision

Use Play-Nice as the **machine cooperation language** for the fresh-ground Worlds rebuild.

Worlds keeps only product words that add product meaning:

```text
Home · Connect · Memory · Settings
```

Everything below that should use a Play-Nice word or shape when one already
exists. If Worlds invents a parallel synonym, the burden of proof is on the
new word.

This is a clean-break rebuild. Compatibility with retired Worlds internals is
not a goal.

## Why now

The existing Worlds interface has not been a usable product surface. The
front-door rebuild is already replacing the interface and deleting old
application structure.

This is the cheapest point to remove vocabulary drift, duplicate schemas and
compatibility glue instead of teaching the new UI about them.

Git is the archive. The new core does not need to carry the old furniture.

## Language layers

### Play-Nice owns shared machine meaning

Use the canonical Play-Nice concepts directly where they apply:

- participant
- capability
- room
- card
- need
- action
- approval / permission / grant
- evidence
- history
- shared status vocabulary
- UNKNOWN as a real state

The status vocabulary is the closed `play-nice/status-v1` set:

```text
healthy warning needs_attention degraded unavailable
not_configured disabled stale unknown

working waiting blocked deferred partial complete failed
```

Provider/native status words translate into this set at the boundary once.

### Worlds owns product language

Worlds may keep product nouns that Play-Nice intentionally does not define:

- Home
- Connect
- Memory
- Settings
- Companion / character presentation
- Worlds-specific durable-memory concepts where no Play-Nice contract owns
  the meaning

These are product concepts, not a second interoperability vocabulary.

### Native systems keep native language at the edge

A Play-Nice room remains a **Room** on the wire.

A vendor API may call something an alert, job, device, incident, pipeline or
deployment.

Adapters translate those concepts into the shared kernel. The core does not
adopt vendor vocabulary.

## Target shape

```text
external/native systems
        │
        ▼
  adapters / gateways
  translate once
        │
        ▼
┌───────────────────────────────┐
│ Play-Nice semantic kernel     │
│                               │
│ Participant                   │
│   └─ Capability               │
│       └─ Room                 │
│           ├─ Card             │
│           ├─ Need             │
│           └─ Action           │
│                 │             │
│              Approval         │
│                 │             │
│               Result          │
│                 │             │
│              History          │
│                               │
│ status = play-nice/status-v1  │
└───────────────┬───────────────┘
                │
                ▼
     Home · Connect · Memory · Settings
                │
                ▼
        plain human language
                │
                ▼
      character / companion voice
```

Presentation may translate machine truth into plain words and personality.
Presentation never creates new machine state.

## Ports and adapters

The core must be testable without a browser, vendor API, Room implementation,
or deployment environment.

Outside systems connect through narrow adapters/gateways. Their private API
shape does not leak into the core.

A compatibility requirement belongs in an adapter. It does not justify a
legacy concept in the new kernel.

## One truth for API shapes

FastAPI/Pydantic is the server-side schema source.

The generated OpenAPI document is the cross-language contract.

TypeScript API shapes are generated from OpenAPI and imported by the UI.

Do not maintain a second handwritten copy of an API response/request model in
`ui/src/fd/types.ts` when the generated schema can express it.

Handwritten TypeScript is for **view models and presentation-only state**, not
copies of server contracts.

## Delete-first rule

For every old model, endpoint, helper, adapter, UI type or compatibility path:

1. identify the behavior/contract it protects,
2. decide whether the new product still needs that behavior,
3. preserve the acceptance test or rule if yes,
4. delete the implementation by default,
5. rebuild the smallest version on the new kernel only when the new UI needs it.

No "temporary compatibility layer" without a named consumer, removal gate and
issue.

## What this supersedes

This decision narrows the C1/C2 provider/request/card machinery in
`docs/rebuild/CONTRACTS.md`.

Those contracts remain evidence of what was learned about confinement,
durability, authority, stale data, failure isolation and accessibility.

Their nouns and file shapes are **not automatically preserved**.

The new design should keep the earned constraints while re-deriving the
smallest model.

## What must survive

Fresh ground does not mean forgetting lessons.

Preserve:

- public/private safety boundary
- owner identity + tested local recovery path
- explicit permission and step-up for consequential work
- at-most-once / idempotency safety where consequences require it
- honest UNKNOWN and stale state
- failure isolation
- deterministic Memory baseline, export and restore
- accessibility + sensory floors
- Play-Nice Room interoperability
- Project Home authority for operations it owns
- provenance/history for consequential changes

## What may die

Unless a current requirement proves otherwise:

- old Bridge / Workshop / Crew UI language
- duplicate provider-specific status vocabularies
- handwritten UI copies of API schemas
- old config shapes preserved only for compatibility
- provider/request abstractions that exist only because the old UI needed them
- adapters for retired consumers
- documentation that describes deleted structures
- compatibility tests whose only purpose is preserving the retired application

## Cutover

This ADR authorizes source restructuring on `rebuild/front-door`.

It does **not** authorize production cutover, deployment, secret changes or
destructive data migration.

Production remains an explicit owner decision after the rebuilt surface is
usable and its acceptance gates pass.

## Evidence behind the shape

The design intentionally matches established ports/adapters and
anti-corruption-layer practice: outside technologies translate at explicit
edges while the application keeps its own small model.

FastAPI already produces OpenAPI 3.1 from Pydantic models, and current client
tooling can generate TypeScript types/clients from that schema. The rebuild
already generates `ui/src/generated/api-types.ts`; the next step is to make
that generated contract real rather than decorative.

Research notes and links live in
[`docs/rebuild/PLAY-NICE-KERNEL-PLAN.md`](../rebuild/PLAY-NICE-KERNEL-PLAN.md).
