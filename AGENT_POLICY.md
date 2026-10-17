# Agent Policy — Worlds Decision Kernel

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the agent decision policy (product/decision/ownership/security rules and the definition of done) · **Read this if:** you are an AI agent deciding what to do here, or how to say whether it worked.

**In short:** the mandatory entry point for agents. It states how Worlds makes decisions — what the person wants over what a provider's UI suggests, admitting uncertainty over making things up, explicit ownership, and failing safe on security. It also gives the report format to end substantial work with. It does not copy the contracts; it tells you to load them.

(Formerly "Personal World" — product renamed 2026-09-12; technical identifiers unchanged. Direction is owned by `.project/PLAN.md`, which supersedes TRUE-NORTH's scope and sequencing.)

## Mandatory preflight

Before planning, researching, designing, modifying, reviewing, merging, or releasing:

1. Read [`AGENT_CONTRACTS.md`](./AGENT_CONTRACTS.md), the repository's canonical contract index.
2. Load every applicable contract, especially Accessibility and Human Reliability.
3. Load the canonical contract text: Accessibility, Human Reliability (`docs/HUMAN_RELIABILITY_CONTRACT.md`), and every other applicable contract.
4. Inspect current repository behavior before trusting old handoffs or assumptions.
5. Identify whose state, data, or experience a change affects.
6. Determine how the result will be verified.

**What the repo shows beats what you infer. "Unknown" is a valid answer. Say you don't know rather than guess.**

## Product rule

Worlds is a personal appliance, not an administration console.

Technology should disappear behind understandable human concepts.

Prefer:

`human intent → native Worlds concept → adapter`

over:

`provider → provider-shaped UI`

Examples:

- source control, not a Gitea/GitHub clone
- health, not a Gatus clone
- deployment state, not a Komodo clone
- safe secret state, not a vault clone
- personal memory, not a vector-database console
- settings and drift, not a configuration-management dashboard

## Decision rule

Prefer designs where:

- the correct behavior is the easiest behavior
- looking up the real answer is easier than making one up
- accessibility is the default
- private state is private by default
- ownership is explicit
- uncertainty remains visible
- recovery is understandable
- complexity is progressively disclosed
- users do not need infrastructure knowledge for ordinary use
- single-user operation stays simple even as multi-user capabilities grow

## Contracts are requirements

The canonical contract/index system governs decisions.

Always consider:

- Accessibility
- Human Reliability
- security/privacy
- identity and ownership
- public repository boundaries
- recovery and reversibility
- provider-neutral architecture

Do not duplicate canonical contracts here.

## Human experience

Before accepting a design, ask:

- What does the person think is happening?
- What actually is happening?
- Can those differ silently?
- What needs attention?
- What can safely wait?
- What is healthy?
- What is unknown?
- Can the person recover without understanding implementation internals?

Accessibility requirements are architectural requirements, not polish.

Do not weaken accessibility floors for visual preference or implementation convenience.

Use progressive disclosure.

Keep the interface simple without hiding important information.

## Ownership

For state that can become personal, always ask:

> Whose state is this?

Design new capabilities so identity, profile, ownership, permissions, memory, agents, integrations, preferences, and sharing can have explicit boundaries.

Do not create architecture that assumes all state is globally owned if it is reasonably likely to become user-specific.

## Security

Never expose:

- credentials
- tokens
- secret values
- resolved secret configuration
- private memory belonging to another boundary
- sensitive provider payloads

Fail closed when authorization or ownership is ambiguous.

Administrative capability must not automatically imply routine access to private content.

## Simplicity

Before adding a new service, framework, database, agent system, or UI, ask whether an existing Worlds or Lab abstraction already owns the responsibility.

Prefer:

- small files
- explicit schemas
- boring APIs
- deterministic logic
- native Worlds concepts
- provider adapters
- ordinary Git
- visible state

Do not introduce complexity merely because an AI agent can manage it.

## Definition of done

When applicable:

`implement → test → accessibility check → security/ownership check → docs → review → CI → merge → deploy → verify`

Evaluate relevant contracts as:

- `PASS`
- `FAIL`
- `N/A`
- `UNKNOWN`

Never silently convert `UNKNOWN` into `PASS`.

## Final report

Substantial work ends with:

**CHANGED:** actual changes  
**VERIFIED:** evidence  
**CONTRACTS:** contract status  
**ACCESSIBILITY:** relevant verification  
**OWNERSHIP/SECURITY:** relevant verification  
**UNKNOWN:** what is still not known  
**DEFERRED:** intentional future work  
**NEXT:** legitimate next action or `nothing required`

## Core principle

> **Make saying "I don't know" easier than making something up.**

Worlds should make the safe, accessible, accurate and understandable choice the easiest one, for its users and for the agents building it.
