# Historical receipts and handoffs

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the `docs/history/` archive index (what is here and why it is not current) · **Read this if:** you are looking for a dated receipt or need to know what not to trust.

**In short:** this folder holds archived 2026-09-12→14 construction, merge and convergence receipts. They are historical evidence, not current authority — their counts have drifted. This page is the map of what is here and where current truth lives.

Archived evidence from the 2026-09-12→14 construction, merge, and
convergence epochs. These files are **historical**, not current
authority. They are preserved
because they record what an agent believed and verified at a point in
time; they are not maintained and their counts will drift from code.

For current truth, use:

- **Current state pointer:** [`../../.project/CURRENT.md`](../../.project/CURRENT.md)
- **Architecture:** [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- **Verified wiring map:** [`../repo/WIRING-READINESS.md`](../repo/WIRING-READINESS.md)
- **Repo inventory:** [`../repo/REPOSITORY-INVENTORY.md`](../repo/REPOSITORY-INVENTORY.md)

## Why these were archived

They are one-off merge receipts and pre-merge handoffs whose claims
(tool counts, test counts, screen counts, endpoint dispositions) were
superseded within the same epoch and, in several cases, contradicted
each other. `docs/repo/REPOSITORY-INVENTORY.md` records the
contradictions. Keeping them in the canonical `docs/` root made stale
numbers look like current authority.

| File | Date | What it was |
|---|---|---|
| [`FINAL-RECEIPT.md`](FINAL-RECEIPT.md) | 2026-09-13 | Merge receipt; claimed 726 tests / 29 tools / 15 screens / 18 capabilities. |
| [`FULL-SYSTEM-INVENTORY.md`](FULL-SYSTEM-INVENTORY.md) | 2026-09-13 | Earlier "generated from live codebase" inventory; claimed 663 tests / 19 read tools / 14 screens / 78 endpoints. Least current of the set. |
| [`CONNECTIONS-RECEIPT.md`](CONNECTIONS-RECEIPT.md) | 2026-09-13 | Connections/Providers audit receipt (725 tests, 18 providers). |
| [`RECONCILIATION-RECEIPT.md`](RECONCILIATION-RECEIPT.md) | 2026-09-13 | Post-Connections reconciliation receipt (HEAD `f73df40`). |
| [`MERGE-DOCS-RECEIPT.md`](MERGE-DOCS-RECEIPT.md) | 2026-09-13 | Merge + issue closure + screenshots + docs refresh receipt (719 tests). |
| [`WIRING-COMPLETION-HANDOFF.md`](WIRING-COMPLETION-HANDOFF.md) | 2026-09-13 | Pre-merge wiring handoff with 10 open questions; header notes all were resolved. |
| [`API-WIRING-HANDOFF.md`](API-WIRING-HANDOFF.md) | 2026-09-13 | Endpoint-disposition handoff (68 endpoints, 19 tools). |
| [`CONSTRUCTION-AND-EPOCH-NARRATIVE.md`](CONSTRUCTION-AND-EPOCH-NARRATIVE.md) | 2026-09-12→14 | Dated narrative extracted from `.project/CURRENT.md` (2026-09-15): the feature slices (Projects workspace, journal supersede, agent-sync estate, observation age, Gitea retirement, GHCR), the identity pass, and the integration truth pass. |

## Do not

- Do not treat any count or "status" in these files as current.
- Do not add new receipts here without also linking them from
  `docs/README.md`; new operational evidence belongs in the canonical
  docs it describes, not as a parallel narrative.