# ADR-0003: The Workbench is a core-owned capability (attach-existing, broker-scoped)

> **Status:** Direction · **Verified:** 2026-09-26 · **Canonical for:** the Workbench direction (proposed, review-only) · **Read this if:** you are touching workbench/terminal/exec/preview work.

**Scope note:** proposed and review-only. `.project/PLAN.md` wins on scope and sequencing; this record owns only the decision below.

**In short:** proposed, not accepted. If accepted, the Workbench (terminal · task · preview · artifact) is a core-owned capability over the existing estate — attaching to the existing `ai-distrobox`, with terminal/exec behind a capability-scoped broker, never a raw host shell or container socket. A spike proved the registry seam fits; see `docs/adr/WORKBENCH-SPIKE-FINDINGS.md`.

- Status: **proposed** (review-only per owner D22; not yet accepted)
- Date: 2026-09-21
- Supersedes: none
- Enforced by: `personal-world framework validate`, `tests/test_framework.py`, the terminal/exec broker
  boundary contract (to be written when built)
- Normative doc: `docs/NATIVE-BASELINE-AND-ENRICHMENT.md` (extends ADR-0001 to workbench tooling)

## Context

Owner direction (human, 2026-09-21): **Worlds is the place Rylee works directly; other machines are
attached resources.** Normal AI/dev/build/document work should happen in a directly attached Workbench
that feels near-native. Rylee already runs her Linux tooling inside Distrobox (`ai-distrobox`,
`homelab/tools/distrobox/`), so this is *wrapping an environment she already prefers*, not inventing a
virtual-workstation abstraction. **The Workbench is not secondary to the Node/Agent work — it is the
product direction; the Agent extends it.** The existing capability/provider model (ADR-0001) already
governs this shape.

## Decision

1. **`workbench` (with `terminal`, `task`, `preview`, `artifact`) are core-owned, provider-neutral
   capabilities.** They belong to Worlds; providers implement or enrich them.
2. **Native baseline = `not_configured`.** The core boots with zero workspace providers (preserves
   the zero-provider-boot rule). "Feels native" is a *surface priority*, not a boot dependency.
3. **Podman, Dev Containers, Task, and Dagger are `enrichment`/`replacement` providers** behind adapters.
   The first Workbench **attaches to the existing `ai-distrobox`** — no new runtime, no new installer.
4. **Terminal/exec go through a capability-scoped broker** (allow-listed commands, scoped workdir,
   container-confined) — **never** a raw Podman/Docker socket, **never** arbitrary host shell.
   "Open Host Shell" is an explicit, separate privileged path.
5. **Worlds does not become an RMM.** The Workbench is the primary surface; the Node/Agent layer exists to
   extend it, not to replace it.

## Consequences

- The thin slice attaches to `ai-distrobox`; disposable/spec-provisioned workspaces are a **later
  enrichment, not a fork** (the container boundary is recorded so provisioning later does not diverge).
- Reuses the existing `lab world`/`lab_personal_world.py` seam and the journal for task/event state.
- Future cost: the broker boundary contract must be written before any terminal/exec ships; it is the one
  genuinely new security surface this direction adds.