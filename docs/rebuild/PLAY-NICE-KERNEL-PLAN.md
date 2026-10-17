# Play-Nice kernel rebuild plan

**Target:** `rebuild/front-door`  
**Decision:** [ADR-0009](../adr/0009-play-nice-semantic-kernel.md)  
**Mode:** deletion-first fresh-ground rebuild

## Outcome

Make Worlds easier for people **and** agents to understand by shrinking the
machine model.

The target is not "replace every noun with a Play-Nice noun."

The target is:

> **When Play-Nice already owns a shared meaning, Worlds uses it. Worlds invents
> only product language. Native/vendor language stops at adapters.**

The implementation should leave less code than it starts with.

## Research basis

### Ports and adapters

Alistair Cockburn's ports-and-adapters architecture separates the application
from UI, databases and external technology behind explicit ports/adapters so
the application can be tested independently:

- https://alistair.cockburn.us/hexagonal-architecture

This matches Play-Nice's rule that participants may stay different while a
translation layer preserves shared meaning.

### Anti-corruption layer / gateway

Martin Fowler describes gateways/anti-corruption layers as the translation
between a foreign context and the application's own vocabulary:

- https://martinfowler.com/articles/gateway-pattern.html
- https://martinfowler.com/bliki/DomainDrivenDesign.html

Worlds should not ingest a provider's private nouns simply because an API
exposes them.

### Generated API contract

FastAPI generates OpenAPI from declared models and explicitly supports
generating TypeScript clients from that schema:

- https://fastapi.tiangolo.com/advanced/generate-clients/
- https://fastapi.tiangolo.com/tutorial/first-steps/

`openapi-typescript` supports generated TypeScript types and typed clients
from OpenAPI:

- https://openapi-ts.dev/introduction
- https://openapi-ts.dev/examples

Current Worlds already runs `ui/scripts/generate-api-types.mjs` and produces
`ui/src/generated/api-types.ts`, but the front-door UI still maintains a
large handwritten `ui/src/fd/types.ts` with duplicate API shapes.

That is our first measurable compression seam.

## Ground rules

1. **Delete before adapting.**
2. **Play-Nice shared word before Worlds synonym.**
3. **Worlds product word before vendor word.**
4. **Adapter translates once.**
5. **Generated schema before handwritten cross-language type.**
6. **One shared status vocabulary.**
7. **Human wording comes from machine truth.**
8. **Character adds voice, never state.**
9. **Compatibility requires a named current consumer.**
10. **Fewer concepts is a feature.**

## Phase 0 — inventory and deletion map

Do not refactor yet.

Produce a checked-in machine-readable inventory of current rebuild concepts:

- Pydantic/API models
- public API endpoints
- UI handwritten API types
- generated OpenAPI types
- config object kinds
- provider/Room adapters
- status/error vocabularies
- authority/action lifecycle nouns
- old compatibility-only tests/modules

For each concept classify:

```text
PLAY_NICE      shared meaning already exists
WORLDS         genuine product concept
ADAPTER        foreign/native compatibility
DERIVED        generated view/type
HISTORICAL     delete after evidence is preserved
UNKNOWN        needs inspection
```

### Exit

No implementation starts until every current core noun is classified.

## Phase 1 — one status kernel

Create one status module derived from / checked against
`play-nice/status-v1`.

Remove local status enums that are only subsets/synonyms where practical.

Rules:

- health and progress remain distinct
- state carries source + observed time where applicable
- provider-specific words translate at the adapter
- human text maps at presentation
- character text maps after plain human wording
- no UI component invents status semantics

### Exit

A repository search can identify one owning machine vocabulary and tests fail
if a new unapproved status word appears.

## Phase 2 — generated API types become real

Current seam:

```text
Pydantic
  → OpenAPI JSON
  → generated api-types.ts   [exists]
  + handwritten fd/types.ts  [duplicates contracts]
```

Target:

```text
Pydantic
  → generated OpenAPI
  → generated TypeScript API contract
  → small UI view models only
```

Work:

- generate OpenAPI from the actual front-door application, not a manually
  maintained parallel spec
- make generation deterministic in CI
- import generated API types in the front-door UI
- shrink `ui/src/fd/types.ts` to presentation/view-model concepts
- add a drift check: generated output must be clean after generation
- prefer `openapi-fetch` or the existing equivalent typed client path rather
  than repeated hand assertions

### Exit

Changing a server response shape changes the generated client type and breaks
the UI compile if the UI has not adapted.

No human must edit the same API field in Python and TypeScript.

## Phase 3 — replace Provider/Request-first core with shared concepts

Do not mass-rename.

Derive the smallest model from actual UI needs and Play-Nice:

```text
Participant
Capability
Room
Card
Need
Action
Permission / Approval
Result
History
```

Questions to answer with code evidence:

- Does `Provider` add meaning beyond "participant/connection adapter"?
- Does `Request` belong only inside HTTP/native adapters?
- Can Connect operate on capabilities/rooms rather than request internals?
- Can Home consume Cards/Needs without knowing the transport?
- Can Action execution use the Play-Nice identity/permission language instead
  of a second authority vocabulary?
- Can Room remain the shared wire contract while HTTP/OpenAPI/native systems
  are adapters into the same core?

### Exit

Home cannot tell whether a Card came from HTTP, room/0, Project Home or a local
source without inspecting provenance/detail.

Connect may expose implementation detail progressively, but core rendering and
state do not branch on provider transport.

## Phase 4 — rebuild Connect around capabilities

Connect should answer:

```text
What can I connect?
What does it add?
What does it need?
Is it working?
What can I do next?
```

Not:

```text
Which internal request/config object would you like to edit?
```

Keep the deep mechanics reachable for advanced use.

Use Play-Nice:

- capabilities-not-vendors
- versions-and-discovery
- setup-checks-itself
- calling-other-services
- room
- what-why-next
- depth-on-demand

### Exit

A new supported system can be integrated by adding an adapter/Room without a
new top-level UI concept or new status vocabulary.

## Phase 5 — authority language cleanup

Preserve the hard safety properties. Re-derive the names.

Prefer Play-Nice concepts:

- actor
- permission
- scope
- grant
- approval / step-up
- action
- result/history

Avoid generic overloaded fields where a more specific word exists.

Keep Project Home authority explicit for the operations it owns.

### Exit

A reviewer can read one action flow without learning a second home-grown access
control vocabulary.

## Phase 6 — presentation and character layer

Only after the machine kernel is stable.

```text
machine truth
  → plain Worlds wording
  → optional character/companion voice
```

Examples:

```text
needs_attention
→ "Needs your attention"
→ "I found one thing with your name on it."
```

The last sentence is presentation. It cannot be parsed back into state.

### Exit

Turning character/theme off changes no machine state, route, authority rule or
accessible meaning.

## Phase 7 — delete the old furniture

For every compatibility path retained during the migration, require:

- named current consumer
- removal condition
- owner issue
- regression test proving why it still exists

Delete:

- unused old config models
- retired endpoints
- duplicate TS API types
- old UI compatibility helpers
- old status translations outside adapters
- tests that protect behavior explicitly rejected by ADR-0009
- docs whose only job is explaining deleted machinery

Git history is the archive.

### Exit

The fresh-ground core is smaller by meaningful measures:

- fewer handwritten schema/type declarations
- fewer core nouns
- fewer transport branches in UI/core code
- fewer compatibility modules
- no duplicate current-state/status vocabulary

Do not chase an arbitrary line-count target. Record before/after counts as
evidence.

## Suggested work packets

These can run serially. Do not parallelize shared-model changes.

### Packet A — vocabulary inventory

Owned paths:

- `src/personal_world/worlds/`
- `ui/src/fd/`
- `ui/src/generated/`
- `docs/rebuild/`

Deliverable: classification inventory + proposed deletion map. No behavior
change.

### Packet B — schema/type single source

Own the OpenAPI generation + UI type seam. No product-language refactor yet.

### Packet C — status kernel

One Play-Nice status owner + adapter translations + presentation mapping.

### Packet D — semantic core

Rebuild the internal model around Participant/Capability/Room/Card/Need/Action
and remove transport-shaped concepts from core paths.

### Packet E — Connect

Rebuild the user-facing Connect experience on capabilities and setup checks.

### Packet F — deletion

Remove superseded models/endpoints/types/docs/tests after all new gates pass.

## Safety / authority

This work may restructure source on `rebuild/front-door`.

It may **not**:

- cut over production
- deploy production
- mutate production data
- rotate secrets
- weaken owner step-up or Project Home authority
- silently migrate personal Memory data
- remove rollback/preservation handles needed for the cutover

Those remain separate owner-gated actions.

## Acceptance for the whole experiment

The experiment succeeds if:

1. the new UI can be built on the kernel without resurrecting old concepts,
2. Play-Nice status and Room semantics remain conformant,
3. UI API types are generated from server truth,
4. provider/native vocabulary stops at adapters,
5. no vendor/provider outage blanks unrelated product state,
6. Home/Connect/Memory/Settings remain stable product landmarks,
7. character can be removed without changing semantics,
8. the relevant full backend/UI/accessibility/public-safety suites pass,
9. source code and handwritten schema surface measurably shrink,
10. Rylee can actually use the resulting interface.

That last one outranks architectural elegance.
