# docs/vnext — index

> **Status: index only.** Nothing here is a running system. It points at vnext's documents and
> states each one's own status word. It adds no claim of its own.

vnext is the Worlds front door's design-and-plan lane. Cleanup ran first (`retire.md`); the design
and the API contract exist as merged documents, not as running code. The build plan is the sequence
that would turn them into one.

| Document | Status | What it is |
|---|---|---|
| `docs/vnext/connect-contract.md` | **MOCKUP** | The Connect contract (#329): six verbs, the typed shape, the endpoint list, the field ledger, the threat/authority tables, the persistence story (§6.1). No route, field or security test in it exists in code. |
| `docs/vnext/build-plan.md` | **PLAN ONLY** | The bounded build sequence (d-plan): numbered steps, the protected-code card for Rylee, what the proofs do and do not establish, explicit unknowns, and what is deliberately not planned. |
| `docs/vnext/proof/c-proof.md` | **DRAFT proof** | The Stage C read-only, synthetic proof of the contract, with the two unmet Sol conditions pinned as strict `xfail`. |
| `docs/vnext/proof/c-room0.md` | **DRAFT proof** | Project Home as the contract's room/0, read-only and synthetic, across the zero-provider, stale/unknown and revoked states. |
| `docs/vnext/retire.md` | **Current** | The Stage 0 keep-or-retire ledger: what was retired as provably dead, with its consumer proof and rollback, and what is deliberately kept. |
| `docs/vnext/worlds-design.md` | **MOCKUP** | The Worlds front-door design (screens, words, states) over synthetic fixture data. |
| `docs/vnext/inventory.md` | **Current** | Ownership and disposition of the front-door core, with unknowns listed in §10. |
| `docs/vnext/reviews/2026-10-16-connect-contract-review.md` | **REVIEW** | Rylee's requested contract review (#323): what the Connect contract promises against what the code does at `39beedb`, the gaps, and the questions — including the two MAJOR findings and the citation drift. Not an approval; nothing in it amends the contract. |

Companions this index does not restate: `connect-contract-rereview.md`, `contracts-audit.md`,
`docs-truth.md`, `full-design-brief.md`, `preserved-branch.md`, `worlds-design-CRITIQUE.md`, and the
`prototype/` and `visuals/` directories.

Status words stay honest: MOCKUP ≠ PROTOTYPE ≠ APPROVED; merged ≠ tested ≠ deployed; a step that has
not run is planned, never done.
