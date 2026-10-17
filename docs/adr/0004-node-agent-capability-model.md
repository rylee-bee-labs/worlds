# ADR-0004: Node & Agent capability model (the Agent is the enabler, not the product)

> **Status:** Direction · **Verified:** 2026-09-26 · **Canonical for:** the Node/Agent vocabulary and boundary (proposed, review-only) · **Read this if:** you are working on Nodes, remote machines, or the Worlds Agent.

**Scope note:** proposed and review-only. `.project/PLAN.md` wins on scope and sequencing.

**In short:** proposed, not accepted. If accepted, remote and host machines appear as **Nodes** reachable through a small **Worlds Agent** that advertises capabilities and delegates mechanics to open tools. Mesh presence never grants Worlds-level authority, and an offline Node never breaks the core. No Agent ships yet.

- Status: **proposed** (review-only per owner D22; not yet accepted)
- Date: 2026-09-21
- Supersedes: none
- Enforced by: capability manifest (`/api/manifest`), the Node/Agent contract (to be written when built)
- Normative doc: `docs/NATIVE-BASELINE-AND-ENRICHMENT.md`; Play-Nice `capability-first`,
  `failure-and-degradation`

## Context

Owner direction (human, 2026-09-21): remote/host machines appear as **Nodes** reachable through a small
**Worlds Agent**. The Agent extends the Workbench to host-native and remote capabilities. **The Agent is
not the product** — the primary-viewport / Workbench experience is. The Agent must stay small and healthy,
delegating mechanics to existing open tools rather than reimplementing them.

## Decision

1. **Vocabulary, not services.** `Node`, `Workspace`, `Volume`, `Service`, `Task`, `Artifact`,
   `Capability` are **data-model vocabulary** over the existing capability/manifest/journal model — not
   eight new services with their own stores.
2. **The Agent implements only Worlds-specific capabilities:** node identity, pairing, presence, capability
   advertisement, host telemetry, native OS actions, service orchestration, power, GPU controls, native app
   launch, desktop-session brokerage, task/events, Vault step-up mediation, tool supervision/health.
   It **delegates mechanics:** networking → NetBird · terminal → SSH · remote files → SFTP/rclone ·
   containers → Podman · dev spaces → Dev Containers · simple builds → Task · complex builds → Dagger ·
   secrets → OpenBao · backup → restic · desktop protocols → RDP/VNC/guacd.
3. **Capabilities are OS-negotiated** (no Linux-only assumptions). A Node advertises what it can do; Worlds
   authorizes per-capability. Unrestricted administration is an explicit shell/remote session, not the
   normal automation path.
4. **Two identities, kept separate.** NetBird answers *"is this computer allowed on the mesh"*; the Worlds
   Agent answers *"what is this Node allowed to do inside my World."* Mesh presence never grants
   `desktop.control`, `service.restart`, `vault.request`, or `host.reboot`.
5. **Enrollment:** install Worlds Node → agent presents a pairing code → Rylee approves in Worlds →
   Worlds issues a short-lived NetBird enrollment key → NetBird joins the mesh → key expires/discarded →
   agent registers its Worlds identity (node certificate) → Node ready. No shared lab-wide admin password.
6. **"Worlds Node" = one user-facing install** containing the Worlds Agent + the NetBird client as
   **separate cooperating components**. The agent talks to the local NetBird daemon through its supported
   local API (gRPC / HTTP-JSON daemon socket) — never by scraping UI state.
7. **Offline Node ≠ broken Core.** A Node may disappear without breaking Worlds; report the real
   `unavailable`/`stale` (canonical `failure-and-degradation`).

## Consequences

- The cross-platform Node package (Windows/macOS/K2), remote desktop, and general RMM breadth are
  **post-1.0**; the first proof is one Bazzite Node + one genuine host capability.
- The Agent stays a small, healthy daemon; mechanics live in replaceable open tools.
- Future cost: the Node/Agent capability contract + the two-identity authorization boundary must be written
  before any Agent ships.