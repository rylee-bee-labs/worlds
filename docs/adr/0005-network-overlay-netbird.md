# ADR-0005: Network overlay behind a `NetworkOverlay` contract (Headscale + Tailscale; NetBird dropped)

> **Status:** Direction · **Verified:** 2026-09-26 · **Canonical for:** the replaceable network-overlay direction (proposed, review-only) · **Read this if:** you are touching mesh networking for Nodes.

**Scope note:** proposed and review-only. `.project/PLAN.md` wins on scope and sequencing. (Filename keeps the original `netbird` slug; the decision dropped NetBird.)

**In short:** proposed, not accepted. If accepted, Worlds owns a generic `NetworkOverlay` contract, first implemented by `HeadscaleAdapter` (BSD-3 `juanfont/headscale` + BSD-3 Tailscale clients, no paid gate); NetBird was dropped for its open-core paid tier and AGPL relicensing. Nothing ships; the first slice uses SSH + the existing `lab` CLI.

- Status: **proposed** (review-only per owner D22; license gate cleared)
- Date: 2026-09-21 — **supersedes** the same-day NetBird-preferred draft
- Enforced by: the `NetworkOverlay` adapter contract; `personal-world framework validate`
- Normative doc: `docs/NATIVE-BASELINE-AND-ENRICHMENT.md`; ADR-0001 (replaceable providers)

## Context

Owner rules: no core capability behind a paid/Enterprise gate; prefer fully-open, easy, self-hostable;
"a cloud VPS layer to run the coordinator, controlled through Worlds." Fresh-data pin (retrieved 2026-09-21,
primary sources):

- **NetBird** is **open-core** — self-hosted has a free Community Edition *plus* a **Commercial/Enterprise
  tier** gating "advanced features" (a 2026 trade article cites ~€2,000/yr "Commercial Starter"); it also
  relicensed BSD-3 → **AGPLv3** (their announcement, 2025-08-04). → trips the no-paid-gate rule. **Dropped.**
- **Tailcat** (`tailscale/tailcat`, **BSD-3**, open-sourced Aug 2026): "Tailscale without Tailscale" — a
  **point-to-point** netcat-over-WireGuard tool with **no control plane** (connection metadata is exchanged
  out of band). It is **not a coordinator** and has nothing to host/manage as a mesh. It *is* excellent for
  ad-hoc secure **SSH / file drop / port-forward** ("a call to something"). Caveat: **no API/CLI/wire
  stability promises** (young) → pin versions, avoid deep coupling.
- **Headscale** (`juanfont/headscale`, **BSD-3**): the open-source, self-hosted **Tailscale control server /
  coordinator**; Tailscale's own opensource page acknowledges it for single-tailnet self-hosting. CLI + API;
  mature; wide homelab adoption. → matches "coordinator on a VPS, managed through Worlds."

## Decision

1. Worlds owns a generic **`NetworkOverlay`** contract:
   `peers · peer_status · enroll · revoke · routes · dns · policies · connectivity`. Adapters are
   replaceable; Worlds never couples to the backend's data model.
2. **First adapter = `HeadscaleAdapter`.** Coordinator = **Headscale** (BSD-3) on the **Worlds Edge VPS**;
   nodes run **Tailscale clients** (BSD-3, open source). No enterprise/paid gate.
3. **Worlds Edge VPS** runs Headscale (+ optional self-hosted **DERP** relay for NAT traversal + **Caddy**
   for HTTPS ingress). Worlds manages Headscale through its **API/CLI** via the adapter — "the coordinator
   on a VPS, controlled through Worlds."
4. **Tailcat** is a *complementary* point-to-point tool, **not** the overlay: a candidate for the lightweight
   remote **terminal / file-drop / port-forward** capabilities (ADR-0004), behind its own capability
   adapters, with the stability caveat. It does not replace the coordinator.
5. **External-service boundary** — no overlay or tailcat code linked into Worlds; CLI/API only. MagicDNS /
   routes / relay come from the overlay, never reimplemented.
6. Does **not** replace the existing **AmneziaWG** road-warrior VPN (`homelab/compose/vpn.yml`); scoped
   separately (overlay = Node mesh + service pathing; AmneziaWG = hostile-network tunnel).
7. **Legal note (scoped):** the "Tailscale + Headscale enterprise legal concern" is about **reselling a
   commercial service** on the protocol/brand — **not** personal self-hosted use (BSD-3, unrestricted).
   Rylee's use is personal/homelab.

## Consequences

- Replaces NetBird cleanly (same contract, swapped adapter); fully open, no paid gate; coordinator-on-VPS is
  native to Headscale.
- Headscale is community-maintained (pin version, watch releases); it is the de-facto standard self-hosted
  Tailscale coordinator.
- Tailcat's unstable API → use for tolerant point-to-point capabilities, pin, don't deep-couple; revisit as
  it matures.
- Acceptance still sequenced behind the Workbench thin slice (D22); the **first slice uses no overlay**
  (SSH + the existing `lab` CLI).