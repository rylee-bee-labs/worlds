# Project Worlds — Durable Decisions

Decisions that are RESOLVED and durable — the "why it is this way"
record. Current implementation state lives in
[`.project/CURRENT.md`](./CURRENT.md); the cooperation constitution
lives in [`contracts/adoption.yaml`](./contracts/adoption.yaml)
(Play-Nice Contracts, upstream at
[github.com/Rylee-Bee/play-nice-contracts](https://github.com/Rylee-Bee/play-nice-contracts)).

Each entry records the decision, the date, and the standing reason.
Nothing here is silently reopened; changing a decision means a new
dated entry superseding the old one (append-only, like the journal).

## Product identity

- **2026-09-06 — Capabilities are core-owned; providers are optional
  implementations or enrichments.** (ADR-0001) The core must survive
  the disappearance of every optional integration; enforced by
  `personal-world framework validate` and `tests/test_framework.py`.
  Reason: a personal control plane must never become a disguised
  dependency on one external system.

- **2026-09-13 — "The world knows how loudly to exist" is an
  implementation/design principle, not copywriting.** Workshop v3
  (file `Wbg1rdt9fVCjWAXEKI1pTc`, philosophy artifact 17:8873,
  convergence audit 18:2) is the current implementation design
  authority for all 16 canonical frames, and its emotional-volume
  system (GENEROUS → AMBIENT → PRACTICAL → ATTENTIVE → QUIET) governs
  how loudly any surface may speak. Screens must be evaluated for
  what is visually loudest and whether importance reads as urgency —
  recorded per frame as AUTOMATED/AGENT REVIEW vs OWNER EXPERIENCE,
  never collapsed into one claim. Reason: the convergence process
  (Rylee described the converged design as more magical than she had
  imagined; the audit's register lines) produced volume rules that
  are the design's substance, and tonight's first implementation
  proved they are enforceable in code, not just prose.

- **2026-09-13 — The design-to-code guardrail held, and that outcome
  is the precedent.** The first unattended implementation attempt
  produced zero code because Figma evidence was unavailable. Rather
  than weakening the guardrail, the project established the full
  chain: Figma evidence (both `get_design_context` and
  `get_screenshot` from the desktop Dev Mode MCP server) → repository
  authority (`.project/design/CURRENT.md` + `WORKSHOP-V3-MANIFEST.yaml`)
  → MCP bridge (SSH reverse tunnel, no credentials in tracked files)
  → implementation skill (`personal-world-implement-figma`) → visual
  comparison → D0–D4 report. With the chain in place, the first
  implementation (Today — Quiet Day, `1a1e6ef`) completed in one
  session because ambiguity had been removed in advance. Reason:
  evidence-first made honesty cheaper than fabrication; keep the
  chain mandatory.

- **2026-09-12 — The product is "Project Worlds"; the companion
  character keeps the name "Personal World."** "Project Worlds is the
  environment; Personal World is the companion inside it." Technical
  identifiers intentionally stay `personal-world` (repo slug,
  `personal_world` package, `personal-world` CLI, compose services,
  schema URIs); historical references are preserved rather than
  rewritten. Reason: continuity of tooling and truthful history.

## Milestones

- **2026-09-13 — Workshop v3 implementation milestone: the bridge works.** Today — Quiet Day (Figma node `17:481`) became the first canonical Workshop v3 frame implemented in the working product at commit `1a1e6ef`. This does **not** mark the Workshop v3 rollout complete: design convergence is 16/16, while implementation is 1/16. It establishes that the full design-to-product path works end-to-end: approved Figma design → repository design authority → Figma MCP → `personal-world-implement-figma` → canonical repository components/assets → rendered comparison → D0–D4 acceptance. The first unattended attempt correctly produced zero code when canonical evidence was unavailable; the project fixed the evidence chain rather than weakening the guardrail. Once that evidence existed, the implementation completed quickly while preserving truthful data, accessibility, repository behavior, and explicit reservations where design and implementation authority differed. Engineering acceptance reached D0–D3 PASS; D4 remained intentionally pending owner review. This is the point where Workshop v3 stopped being only a design language and became part of the working world. **The world knows how loudly to exist.**

## Source of truth

- **2026-09-12 — Project Worlds does not compute repository
  publication state itself. It consumes the read-only agent-sync
  project-state interface.** `agent-sync status --all --format json`
  (the pickle project's adapter layer, schema
  `play-nice/repo-status-v1`) is the single authoritative interpreter
  of Rylee's project estate: Git owns Git truth; agent-sync computes
  publication/safe-to-leave/work-state from it; Project Worlds'
  `AgentSyncProjectSensor` only invokes, parses, and normalizes that
  observation (unknown preserved, closed vocabularies enforced,
  exit-1 treated as a valid work-to-do signal); Projects presents,
  Today summarizes, Personal World explains. No second Git-state
  implementation exists inside Project Worlds, and an agent-sync bug
  is recorded + deferred to pickle, never worked around by
  duplicating Git logic. Reason: one computation, one authority —
  drift between tools showing "project state" is a truth failure
  no UI can repair.

- **2026-09-12 — Personal World may understand project state without
  gaining repository mutation authority.** The chat context carries a
  bounded read-only projection of the agent-sync observation; the
  assistant may summarize, explain, compare, and point to Projects.
  It may NOT push, commit, reset, rebase, stash, or clean, and no
  conversational phrasing is interpreted as Git authorization. The
  projects slice added understanding only, not capability; mutation-
  oriented proposal objects are out of scope until a real,
  owner-authorized Projects mutation workflow exists to prepare into.
  Reason: helpful understanding and dangerous reach must be built as
  separate layers — the seam stays closed until it can open with
  provenance.

- **2026-09-12 — Project-state truth and project-state freshness are
  separate dimensions.** WHAT agent-sync observed (publish_state,
  safe_to_leave, tree counts) and WHEN it observed it
  (`observed_at`, rendered as age) never collapse into each other:
  a stale observation of "diverged" is still a diverged observation,
  just not current evidence — staleness never converts state to
  unknown, and state never hides age. The stale marker is calm
  provenance ("may be stale"), never error vocabulary. Reason: old
  evidence is not false evidence, but it must never impersonate
  current evidence — and confusing the two dimensions would lie in
  both directions at once.

- **2026-09-12 — Project Worlds preserves the observation timestamp
  from agent-sync instead of presenting cached/previous observations
  as timeless current truth.** agent-sync's own `observed_at` is the
  only freshness source (no second clock, no freshness database, no
  polling); age is DERIVED at render time (backend
  `agent_sync.freshness()`, ONE frontend helper
  `lib/observation-age.ts`), the staleness threshold reuses the
  product-wide lab_state 30-minute `FRESHNESS` convention
  (asserted by test; no settings surface), and missing/invalid
  timestamps render as honestly unknown rather than fabricating an
  age. Every project-status surface (Projects glance + guts, Today,
  the assistant context) shows WHEN the estate was observed so the
  user never mistakes an old observation for current truth. Reason:
  truth has a timestamp; the UI must carry it, not invent it.

- **2026-09-15 — One Play Nice adoption manifest, at the project-context
  path, re-pinned to the library HEAD at adoption time.** The project had
  two adoption manifests with different pins
  (`.project/contracts/adoption.yaml` v0.6.0 @ `0cee065` vs a root
  `.contracts/adoption.yaml` @ `1c05de4`), and nothing machine-read
  either. Resolved to `.project/contracts/adoption.yaml` — the layout the
  Play-Nice project-context framework itself uses, the path declared by
  `.project/project.yaml`, and the path the session workflow resolves
  against; the duplicate was deleted and every document points at the one
  manifest. The same pass re-pinned v0.6.0 → **v0.7.0** @ `f825ffb`
  (library HEAD at adoption; adds the always-applicable `assume-unknown`
  contract) and re-attested with the real `contractctl` tool:
  `adopt` = ADOPTION VALID, `commit` = CONTRACT COMMITMENT ACTIVE. Reason:
  one authority per subject — a second manifest with a different pin is
  drift no reader can reconcile, and a pin that lags the library silently
  understates the floors the project claims to implement.


## Container distribution

- **2026-09-12 — Project Worlds is distributed as a versioned OCI
  image through GitHub Container Registry.** The portable Compose
  deployment consumes the published image; machine-specific
  integrations live in optional overrides. Tags: `:latest`
  (mutable convenience, refreshed on each successful main publish)
  and `:sha-<full SHA>` (immutable; documented rollback handle).
  Workflow `.github/workflows/publish-image.yml` triggers via
  `workflow_run` after `validate` passes on `main`; it uses
  `GITHUB_TOKEN` with `packages: write` + `contents: read`, no PAT.
  Compose layout: `compose.yaml` is the portable base (image-only,
  no host paths); `compose.dev.yaml` adds `build: .` for local
  development; `compose.homelab.yaml` carries the optional Rylee-only
  enrichment (Lab CLI + Kilo auth file) that previously lived in the
  base file. Rollback by pinning `PW_IMAGE` to a known-good
  `:sha-...` tag. Reason: a single CI build produces an appliance
  that boots on any Docker/Podman host with only a token and a data
  volume; the previous recipe required cloning the source tree and
  binding WSL-only host paths, both of which made the appliance
  non-portable in practice despite its header.

- **2026-09-12 — The published image is `linux/amd64` only.** The
  single host that currently runs Project Worlds is amd64; ARM is not
  in scope. Multi-arch would roughly double CI build cost and time
  without a real consumer. Revisit when an ARM deployment target
  appears. Reason: cheapest path that still meets the actual use;
  Play-Nice `dependency-discipline` and `search-before-inventing`
  forbid speculating complexity.

- **2026-09-12 — The GHCR package is public.** The image carries
  source only — no secrets, no private endpoints, no deployment
  topology (verified preflight against `SECURITY.md` and
  `tests/test_public_safety.py`). Discoverability is a feature, not a
  boundary. Reversible from the GHCR web UI at any time. Reason:
  no security boundary is crossed by publishing the source image
  publicly; private visibility would add an access-handling layer
  for no defensive gain.

## UAT data discipline

- **2026-09-12 — No persisted user data in the test environment until
  the owner calls the product at least beta.** Standing rule (owner
  directive during UAT, task `project-worlds-test-environment` and
  successors): the isolated `project-worlds-test` deployment must not
  accumulate real/persistent personal data. Every UAT walk starts
  from a verified clean slate (`podman compose -p
  project-worlds-test down -v` then `up -d`, with `GET /healthz`
  showing `setup_needed:true` as the proof, printed to the owner).
  Persistence in the test instance is only allowed for a specific,
  named test use case that requires surviving state (e.g. verifying
  restart persistence), and the volume is wiped again immediately
  after that check. Fixture/synthetic data only — `pw-safety`
  discipline applies. Real data waits for a deployment the owner
  has explicitly designated as persistent, which does not exist yet.
  Reason: during UAT the person must never wonder whether what they
  see is leftover state; a confusing slate is a trust failure, and
  Rylee's real data is too valuable to rest in a system whose
  persistence and auth seams are still being walked.

## Workbench & Node direction — the primary-viewport limb (owner update)

- **2026-09-21 — "Worlds as primary viewport" is a named lighthouse on the single Road-to-1.0; the
  Workbench/Node/Agent work is a limb over the existing homelab estate, not a second infrastructure
  platform.** Owner decisions D21–D24 (human, all-hands #7, `STAFF-MEETING-7-ALL-HANDS-REAL-WORLD-2026-09-21.md`):
  - **D21 (merge):** one canonical direction. The studio `ROADMAP.md` (Road-to-1.0) is the single roadmap;
    "Worlds as primary viewport" is a lighthouse on it. The architecture handoff, the owner-direction
    update, and `WORLDS-DIRECTION-ALIGNMENT-2026-09-21.md` are **folded into** this entry + ADR-0003…0007 +
    the roadmap lighthouse. Staff-meeting and handoff minutes remain **historical records**, not live
    sources of direction.
  - **D22 (flip-first):** the next real implementation proof is the **Station rebuild flip** (foundation).
    ADR/rule alignment proceeds **review-only in parallel**; the Workbench *build* starts after the flip
    lands. The thin slice = attach the existing `ai-distrobox` → Terminal → task/build → streaming →
    preview → artifacts, plus **one** genuine host capability, all on one event envelope.
  - **D23 (consolidate):** canonical direction lives in `ROADMAP.md` + `docs/PERSONAL-WORLD-FINISH-LINE.md`
    + `docs/ARCHITECTURE.md` + `docs/adr/` + this file. Strategy docs are records.
  - **D24 (NetBird, with owner clarification):** NetBird is the **preferred leading prototype** for the
    eventual Node networking layer — **not** a dependency of the first thin slice. Preserved architecture:
    `Worlds Node` = one user-facing install (Worlds Agent + NetBird client as separate cooperating
    components); NetBird = mesh/routing/DNS/relay; Worlds Agent = identity/capabilities/orchestration/
    host-controls/task-events/desktop-brokerage/step-up; Worlds owns a generic `NetworkOverlay` contract
    (never coupled to NetBird's data model); NetBird replaceable; **no core capability on an
    Enterprise/paid-only feature.** Pin the Community/Enterprise + API split before ADR-0005 is accepted.
  - **Governing emphasis (owner, verbatim intent):** *the Workbench is not secondary to the Node/Agent
    work; Worlds is the place I work directly, other machines are attached resources; the Agent/network
    layer extends that environment and must not turn Worlds into an RMM.*
  Reason: the direction had sprawled across parallel documents; this entry + the ADRs are the one canonical
  record so future work grows toward it instead of fighting it. Rationale and detail: ADR-0003 (Workbench
  capability), ADR-0004 (Node/Agent), ADR-0005 (NetworkOverlay/NetBird), ADR-0006 (event envelope),
  ADR-0007 (Vault→OpenBao).

## Product language & interaction contract — owner-approved

- **2026-09-21 — The first-release product language and interaction contract is approved (human, owner
  round table).** Canonical home: [`docs/PRODUCT-LANGUAGE.md`](../docs/PRODUCT-LANGUAGE.md). It refines the
  finish line's older section vocabulary for the first release: **Today → Overview** (the front-page /
  headlines surface, not a competing section) · **Journal/Notes → Memory** (a deterministic place with
  recognizable, assignable icon+word categories, usable with every model off). **Records** (structured user
  information inside Memory; sensitive records lockable; *not* a separate top-level area) is distinct from
  **Vault** (secrets infrastructure) — *Records is not the friendly name for Vault.* Stable skeleton =
  `Overview · Memory · Chat · Settings`; everything else is personal/pinnable sections (owner's own:
  Projects pinned, Music folded into Interests). **Setup/Customize is structural and model-optional**
  ("Customize" inside Settings; "Customize Worlds" as a button elsewhere). Vocabulary: **Run** (not Job) ·
  **Output** (not Result) · **Services** stays · **Computer** (never "Node" in the UI) · "Worlds Agent" is the
  technical name, install language is human ("Connect this computer to Worlds"). Plain default theme:
  **dark-warm**, may carry a recognizable Worlds identity, but lore/companions/strongly-themed illustration
  belong to optional theme packs; **evolve the existing generic-theme work, no new lineage.** Theme boundary:
  themes restyle + add personality but never rename nav / move controls / relocate information / change
  required actions or accessibility semantics — switching themes must not require relearning Worlds.
  Governing principles: *customizable enough to become yours while accessible whether you have a lot or a
  little to give*; *customization must never cost low-capacity recoverability.* **Preserve ≠ promote**; the
  first release is **plain, not tiny.** Reason: the product language had sprawled across competing terms and
  earlier subtraction passes over-cut real spine (Overview, Setup, theme machinery); one approved contract
  aligns presentation without flattening the existing product. The round-table interview is the historical
  source; this entry + `docs/PRODUCT-LANGUAGE.md` are canonical.

## Network overlay — NetBird dropped; Headscale + Tailscale preferred

- **2026-09-21 — NetBird is dropped as the Node networking overlay; Headscale + Tailscale is the preferred
  fully-open alternative (human owner decision + research-desk pin).** Supersedes the "NetBird = preferred
  prototype" line in the Workbench & Node entry above; ADR-0005 rewritten accordingly. Trigger: the owner
  rule *"no core Worlds capability may depend on a paid/Enterprise-only feature."* Pin (2026-09-21, primary
  sources): NetBird self-hosted is **open-core** — a free Community Edition *plus* a **Commercial/Enterprise
  tier** gating advanced features (a 2026 trade article cites ~€2,000/yr "Commercial Starter"); NetBird also
  relicensed BSD-3 → **AGPLv3** (their announcement, 2025-08-04). That trips the no-paid-gate rule → out.
  Replacement: **Headscale** (`juanfont/headscale`, **BSD-3**) — the open-source self-hosted **Tailscale
  control server / coordinator**, acknowledged by Tailscale for single-tailnet self-hosting — + **Tailscale
  clients** (BSD-3). Architecture fit (owner intent): a **cloud VPS ("Worlds Edge") runs the Headscale
  coordinator** (+ optional self-hosted DERP relay + Caddy ingress), **managed through Worlds** via the
  `NetworkOverlay` → `HeadscaleAdapter` contract; any overlay stays replaceable behind it.
- **Tailcat** (`tailscale/tailcat`, **BSD-3**, open-sourced Aug 2026) is recorded as a **complementary
  point-to-point tool, not the coordinator**: "Tailscale without Tailscale" — netcat over WireGuard with
  **no control plane** (metadata exchanged out of band). Strong candidate for the lightweight remote
  **terminal / file-drop / port-forward** capabilities (ADR-0004). Caveat: **no API/CLI/wire stability
  promises** (young) → pin versions, avoid deep coupling.
- Scoped legal note: the "Tailscale + Headscale enterprise legal concern" is about **reselling a commercial
  service** on the protocol/brand, not personal self-hosted use (BSD-3, unrestricted). The first Workbench
  thin slice still uses **no overlay** (SSH + the existing `lab` CLI); Headscale is sequenced behind it.
  Reason: preserves the no-paid-gate + replaceable-adapter rules and the owner's "easy, fully open,
  coordinator-on-a-VPS-controlled-through-Worlds" intent.

## Frontend is Worlds; Station is a theme (navigation reframe)

- **2026-09-21 — "The frontend is Worlds. Station is a theme" (owner, human).** The **stable skeleton**
  (`Overview · Memory · Chat · Settings` + personal sections) is the real, deterministic navigation. The whole
  **star-map / constellation navigation model** (map-as-frontend, seven constellations, drill-through,
  companion orbs, "fly the map to reach a place") moves **out of the core** and into the **later Station theme
  package**. A person must never have to use a spatial map to find something — that was a theme assumption
  that had become load-bearing. **Supersedes master-handoff decision 11 ("Station map = the frontend",
  2026-09-16).**
  - **Station is kept, not deleted** — its palettes, art, companions, and map views remain selectable
    theme/experience packs. Rejected is Station as *default, baseline palette, or required vocabulary.*
  - **Default theme = a complete existing pack, not a hand-built shell.** "Plain" means the **structure**
    (calm, predictable, accessible, low cognitive load) — **not colorless.** Project Worlds ships a **full
    multi-color pack** (all `--pw-*` tokens; the existing set already passes `lab design theme validate`).
    Do **not** author a partial `plain.json` shell (that forces "all the other work" later). Reuse a full
    pack, or generate one via `lab design theme make` only if none feels like home. **The aubergine "station"
    pack is not the default.** **Starting-default pack = `starfield`** (owner, human, 2026-09-21) — a complete,
    validated full palette (deep-navy + warm amber + teal), functionally the amber+teal warm-dark direction,
    already full. Its provenance note "adapted from the constellation portfolio" is an internal lineage tag
    **only** — a *palette carries no lore / companion / star-map navigation*, so choosing it does not
    reintroduce Station; the constellation-*navigation* ban stands independently of palette. (Optional later:
    retitle the default to `Worlds` and neutralize the provenance line — cosmetic.) Other full packs
    (`ocean` / `moss` / `aurora-garden` / `copper-kitchen`) ship as switchable color options. Canonical
    language: `docs/PRODUCT-LANGUAGE.md`.
    Reason: earlier over-subtraction treated real spine as hypothetical and conflated *plain* with *colorless*
    and hand-built a shell; this corrects both and makes the frontend/navigation unambiguously Worlds, with
    Station as one theme among several.

## The rebuild is the shippable product (supersedes D6 "React parked for beta")

- **2026-09-21 — The `pw-vnext-station/ui/` React rebuild is promoted to *the* shippable product; the
  currently-served vanilla `/station/` is experimental and will be retired, not polished (owner, human).**
  Reverses the 2026-09-20 D6 framing ("plain Station centers v1; React spike PARKED as beta candidate —
  no energy until beta"). Reason (owner): "the settings never really worked right on the last one due to
  web inconsistencies… this should be cleaner… wire in the new stuff properly and that's our shippable
  product. current is still experimental after all." The rebuild already has the schema-driven Settings Room
  (prefs→DOM, motion firewall proven both directions, zero-error pipeline); the finicky surface is the one
  we were serving.
- **Definition of done for "shippable" (owner bar, in her words):** *"everything wired to* ***something***,
  and understandable."* Concretely — no floating/dangling piece; every control hits a real endpoint or an
  **honest empty/not-configured state**; no fabricated data or dead buttons; a newcomer (or Rylee on a low
  day) can read any screen and know what it does and where its data comes from. **usable > ceremony** — not
  "hit parity with the throwaway."
- **Consequences:**
  - The D14 big-bang flip gate was a *parity checklist against the served (now-experimental) surface*. With
    the rebuild as the product, that parity is no longer the bar — **re-aim it** to: "does the rebuild wire to
    real/honest endpoints and read as understandable?" Reuse the contract-triage CORE as a *coverage* map, not
    a *parity* jail.
  - **Rylee greenlights rebuilding the API interface if it serves wiring + understandability** — but API/contract
    changes are core-owned + Play-Nice governed with real blast radius (tests, `/api/manifest`, docs). Decide
    them deliberately (route-by-route as wiring demands), not as a speculative rewrite.
  - The genuinely-new *build* work is small and already named in STATE: give `ui/` a real **serve path** in the
    product image (the named flip gap) + fix the **npm peer-dep / storybook version-skew** tree break. Wire the
    rest to the existing backend (the "Lego box" stays; reads open, writes gated).
- **Honest state:** build/serve of the rebuild is **UNVERIFIED this session** — last-verified 2026-09-20
  (preview deployed on a fresh volume, gates green), *not* re-run today; first action is a live grounding pass,
  not assertion.

## Product Council Δ-record (C1–C12) — 2026-09-21, appended per the append-only rule

- **2026-09-21 — The two-week product council ran C1–C12 and changed the product record.
  Full minutes:** `WORLDS-PRODUCT-COUNCIL-2026-09-21.md`. **The plan it produced:**
  `WORLDS-DELIVERY-ORCHESTRATION-PLAN-2026-09-21.md` (supersedes
  `WORLDS-FRIEND-UAT-PLAN-2026-09-21.md` as the *live* delivery plan; the UAT-plan
  file remains as record of Phase-B lanes). Reason: earlier drafts front-loaded the
  friend gate; C2+C7 corrected the sequence to Phase A (Rylee's home, with L-WB)
  → Phase B (friend-safe trial, L12–L16) → Phase C (v2 personality themes on
  stable bones).
  - **C1 (Research Desk):** the only live fact base is `docs/repo/WIRING-READINESS.md`
    (SHA `60823ae`) + this session's read-only probe; earlier prose (STATE, the
    2026-09-16 master handoff) is *context*, not evidence. L16 real friends can
    fail the plan and that's the point; budget goodwill.
  - **C2:** the product's four human moments (Morning / Working / Stressed /
    Curious) are the acceptance frame.
  - **C3:** two new artifacts added as **gates** — the **landmark-stability rule**
    (four skeleton landmarks stay reachable under any customization/theme) and an
    **interruption/resumption fixture** on synthetic data.
  - **C4:** named the **blocking set** for Phase A (three frontend REDs + serve
    path / build repair), the **sequenced** set (registry convergence, chat wiring),
    and the **deferred** set (streaming, tool-calling, overlay/mesh/desktop).
    "Serve today" ≠ "the decided product" — L1 re-cut is required to make the
    frontend match the stable-skeleton contract.
  - **C5:** trust floor before any trial: vault step-up + true-loopback-only + per-instance
    isolation (lab-box multi-instance still shares host) + tear-down-after as an enforced
    lifecycle (not a promise). `vault.enc` portability is an open decision, not a default.
  - **C6:** two more gates added — a tested **degraded-mode state matrix**
    (model-off / provider-dead / node-offline / disk-full → each cell tested, no fake
    green) and a **timed restore drill** that actually brings identities + world +
    journal + vault (after the portability decision) + apps back on a clean box.
  - **C8 (Boring Council):** subtraction pass ran — no new storage/identity/secrets/
    network/CI/mesh enters the friend path. L-WB scope is **hard** (attach `ai-distrobox`,
    one host capability, one journal envelope); drift toward Podman-socket or full RMM
    re-convenes the Council. The `plain.json` shell stays deleted.
  - **C9:** Headscale (BSD-3) chosen over NetBird (AGPLv3 + Commercial tier). Two items
    recorded as **UNVERIFIED → to run** before their lane merges: a live build/serve pass,
    and NetBird's Community-vs-Enterprise split. `starfield`'s "constellation portfolio"
    line is internal provenance; the palette itself carries no lore.
  - **C10:** the **acceptance gates** are named (G-shape · G-real · G-safe · G-memory ·
    G-a11y · G-recover · G-degrade · G-workbench · G-onboard · G-trial) and they become
    the plan's definition of done.
  - **C11:** the friend-UAT (L16) is a consented research instrument with
    feedback→decision routing, *not* a rubber-stamp; the two friends are real people.
  - **C12 (synthesis):** the net product delta is the 4-verb record — **refined**
    (roadmap order: home→friend→v2) · **expanded** (four new gates: stability ·
    resumption · degraded-matrix · timed-restore) · **optimized** (lane split + reuse
    of existing machinery) · **shrunk** (`plain.json` deleted, streaming/mesh
    deferred to Phase C, Workbench is the *one* new capability in Phase A). The
    owner-decision queue at the end of the plan is the live to-do for Rylee.

  Reason: a two-week council should *change* the record. This entry is that change.

## Shared CI harness — 2026-09-21 (L-CI)

- **2026-09-21 — Pipeline plumbing becomes shared machinery; check semantics stay
  repo-owned.** Owner-approved ("I want every part of this to be really clean").
  New lane **L-CI** in `WORLDS-DELIVERY-ORCHESTRATION-PLAN-2026-09-21.md`: a
  private-first `ci-harness` repo exposing `workflow_call` templates
  (python-uv / node-vite / container-smoke) and the single action-SHA-pinning
  source; adopting repos keep a ~15-line contract workflow declaring *their*
  checks (public-safety, lore determinism, contrast-audit stay local concerns).
  Reason (evidence from the same-day estate recon): ~1,829 lines of hand-written
  workflow YAML across four repos with drifted action pins (`checkout@v4.2.2` in
  rylee_lore vs `@v7.0.1` elsewhere), uv-setup re-written per job, homelab
  validate.yml at 699 lines — copy-paste plumbing, not divergent requirements.
  Constraints: the word *harness* in play-nice-contracts already means the
  behavioral-research ledger — naming collision is explicit, README disambiguates;
  homelab and rylee_lore migrations are a later wave (pilot = personal-world via
  draft PR only, never lane-merged); validation requires a **real green GitHub
  run**, actionlint-clean is necessary-not-sufficient; `lab ci` wrapper only if
  it stays cheap. Doctrine applied: adopt the mechanics, own the semantics; keep
  machinery boring; one canonical owner per concern.

## Alpha/beta/RC definitions — 2026-09-22 (roundtable)

- **2026-09-22 — Release vocabulary fixed against the plan's gates** (owner asked
  the team where the project stands on the road to alpha; the roundtable ruled the
  question undefined until mapped, so): **alpha** = all ten G-gates green
  (shape · real · safe · memory · a11y · recover · degrade · workbench · onboard ·
  trial-launcher-safe) AND Rylee uses Worlds as her daily home for a week;
  **beta** = friend-hosted trial passed (G3, real humans + consent);
  **RC** = R6 owner taste-pass ("does this feel like mine?"). Current verified
  state at this entry: G-shape done (d3e6999, eyes-on via Steel browser);
  G-safe backend done (step-up/loopback/isolation, 1218 backend tests green);
  remainder ~35% with critical path Renai-art-fix → L4 → L7 → L-WB → L8 → L11 →
  owner daily-use week. Reason: a percentage without a defined yardstick is
  morale, not engineering. Simulated roundtable; owner authority intact.

## Correctness over preservation + the interface cutover — 2026-09-22

- **2026-09-22 — Owner doctrine adopted as governing rule**: correctness over
  preservation; broken work is deleted or replaced, not patched around; fail
  closed; evidence before completion; existing tests are evidence, not
  authority. Reason: three prior UI pushes each said "done" while the old
  interface kept shipping — completion claims measured artifacts (tests,
  commits), never the user-visible outcome.
- **2026-09-22 — The React rebuild IS the interface, published.** Owner
  directive: no side-by-side, no env-var gate, no localhost. `/` serves the
  rebuild from the container image (node stage builds ui/ → static/app);
  the retired vanilla Station and the frontend/ test suite are deleted from
  the tree (git history preserves them); /station and /vnext only redirect.
  The old suite's axe gate was PORTED, not dropped: axe runs on all four
  landmarks and found three real contrast failures (starfield/ocean/moss
  muted tokens) plus a Tailwind class-slot collision (`text-[var(--pw-…)]`
  compiling font-sizes as invalid colors app-wide) — all fixed; contrast
  audit grew 44→56 pairs to cover the blind spot. Evidence: backend 1325
  green; ui 168/168 + 67/67 e2e + lint 0/0; live container on :8000
  verified by curl AND screenshot. Supersedes the side-by-side policy in the
  2026-09-21 serve entry.

## Owner decision queue — items 1–9 resolved — 2026-09-22

- **2026-09-22 — The full owner decision queue from the delivery plan was
  walked one item at a time (human, Rylee; 9/9 answered).** Execution order
  agreed: record → workbench demo+merge → wizard pass (3+5) → compose volume
  (4) → docs sweep (6) → plain pack (2); items 8–9 deferred to their triggers.
  Nobody commits but the orchestrator; explicit paths only.

  - **Workbench spike (lane `workbench-spike`), three calls:**
    (1) **attach mechanism = (a)** — keep `run_task` synchronous argv-in/
    argv-out as built and tested for the demo; the (b) start-event /
    (c) TTY-attach choice is deferred to the broker contract's first clause
    (crossing the ADR-0006-4 durable/streams trigger knowingly, later).
    (2) **default allowlist = `ai-distrobox` only** on this machine;
    edits to `PW_WORKBENCH_CONTAINERS` / `allowed_containers` are
    step-up-class authorization config, never free UI input;
    per-container command allowlists are broker-contract material, absent
    today. (3) **envelope fit = spike's shape approved as-is** — 5 additive
    optional fields + `JournalKind.TASK` (flat, precedent-following), NOT a
    nested `TaskEnvelope`; `ExecutionViewer` stays its own executions view
    for now (store convergence = a later named call); `payload` keys stay
    minimal (artifacts/workdir/timing unfreeze = later). Merge of the spike
    branch is gated on the live demo being run first.
  - **D2 plain theme (draft `design/PLAIN-DEFAULT-THEME-DRAFT.md`),
    approved with one flip:** **accent = teal `#72B1B1` primary, amber
    `#D4A057` rare highlight** (supersedes the draft's "amber primary"
    proposal — the draft doc's Q1 answer is stale until updated by the
    implementing lane) · surfaces = warm charcoal (faint umber, as drafted)
    · headings keep **Young Serif** serif · **dark-warm only** for the first
    release (light-warm = Phase C) · on validation passing (`lab design
    theme validate`, fails:0 — proposed contrast values are NOT yet
    validated), **`design/themes/plain.json` becomes the first-release
    default pack; `starfield` demotes to a switchable optional pack.**
    **Supersedes** the 2026-09-21 "Starting-default pack = starfield" line
    above and the C8 "the `plain.json` shell stays deleted" note: the shell
    prohibition was against a *partial, colorless* plain — this is a full
    validated pack evolving the generic-theme work (no new lineage), per
    the product-language contract. Same a11y floor: luminance-only status,
    44px, focus ring, reduced-motion.
  - **Setup wizard behavior:** warnings **pause only when blocking** —
    a warning that means the next step genuinely won't work (SSO client-
    secret env var unset; existing `oidc.json` conflict) requires an
    explicit "continue anyway"; informational notes (search index build,
    "available after restart") keep flowing without pause. **No vault step
    in the wizard** — vault setup stays in Settings behind step-up; the
    `init.py` comment claiming "the wizard's richer bootstrap (token +
    vault)" is drift and gets corrected to match the code (token + stores +
    search index only).
  - **Compose config persistence:** the portable base gains a
    **`config-data:/config` named volume** (keeps the 2026-09-12
    "image-only, no host paths" rule intact — no bind mount in the base),
    so wizard-seeded `oidc.json` and `connections.json` survive container
    recreation instead of silently breaking SSO while `setup-complete`
    survives in `world-data`. The two misleading `compose.yaml` config
    comments ("Update config/connections.json", "Copy … oidc.example.json")
    are fixed in the same change; `docs/WORLDS-BACKUP.md` gains the
    in-container note for the new volume. Verification owed: write
    `oidc.json` → `compose down`/`up` → file survives.
  - **First-run naming:** `/setup` and `/login` say **"Worlds"** everywhere
    (title, brand, H1, finish button) — matches the approved
    `PRODUCT-LANGUAGE.md` voice; "Project Worlds" remains the formal name
    in docs/README only.
  - **L13 link collapse: proceed now, scoped as found** (the "owner pending
    doc commit" collision is moot — that work landed as `766d85d`/
    `b7e07fc`/`331b800`/`ab6dfda`). Collapse decorative cross-repo URLs to
    a single safe pointer and **collapse `STATUS.md` and `.agent/STATE.md`
    to one-line pointers** at `.project/CURRENT.md` in the same sweep.
    Security boundary holds: the collapse target carries no private
    topology. Gate: `tests/test_docs.py`.
  - **Five UAT tasks: confirmed as written** (WORLDS-FRIEND-UAT-PLAN §1:
    make it theirs via wizard · add something real · ask AI + model-off
    parity · find by browsing, deterministic · leave-and-come-back).
    No-coaching protocol and the per-task pass/fail/blocked evidence rule
    stand.
  - **Two friends for L16: deferred, not yet named** — re-ask trigger =
    **L14 clean-box passing** (nothing blocked; L16 gates behind L14
    anyway). Real humans, real consent, no rush.
  - **R6 taste-pass: deferred with a trigger** — re-ask when (1) the plain
    pack renders per the D2 calls above with contrast validated AND (2) the
    workbench demo has been run; then one sitting: "does this feel like
    mine?" R6 remains the only final gate before v1.0.
    - **Re-asked and GREEN-LIT 2026-09-22**: both triggers met (plain pack
      `e08ce5c` — `lab design theme validate` PASS fails:0, contrast-audit
      70/0, e2e 67/67 with axe contrast on; workbench demo run pre-merge,
      `472850f`). Owner: "start it now" — orchestrator prepares the eyes-on
      packet autonomously; the taste judgment itself stays the owner's one
      sitting (she is pinged only when there is something worth her eyes).
  Reason: these were the plan's standing owner queue — recorded here so
  every implementing lane cites written truth rather than a chat log.
  Supersessions called out inline per the append-only rule.

## TRUE-NORTH re-vision — 2026-09-22 (owner interview + approval)

- **2026-09-22 — Owner-directed re-focus: `docs/TRUE-NORTH.md` is the
  canonical direction** (human, Rylee; three interview rounds — 18 taps +
  typed answers — after a 24-product research pass across personal
  dashboards, AI companions, git forges, alert-management games, and
  discovery systems). Rulings: north star = **the calm hub, reach
  everything without hunting** (the product sentence stands, narrowed not
  rewritten) · first audience = Rylee, built shareable · **one voice with
  selectable tone registers**; residents + the two-voice system demote to
  an optional personality pack (CHARACTER-HANDBOOK + COMPANION-CANON stay
  as pack canon) · **World Keeper = the one heartbeat** · scope =
  **skeleton-only depth** (Overview · Memory · Chat · Settings) + one
  small "brought to you" discovery card inside Overview ("I love
  interests… if it's not too hard") · specimen surfaces
  (Interests/Map/Media-Music) park honest · Projects parks as a surface
  but Overview project status keeps a deterministic source→details path,
  agent-sync authoritative · Workbench paused behind `PW_WORKBENCH` ·
  **Node/Headscale limb continues** (ADRs 0003–0007 live) · ci-harness
  parked, Play-Nice contracts kept · Workshop portal stays live as estate
  infrastructure with an owner-stated mission (agent work → Rylee's eyes,
  any device, her timeframe) · alpha gates **recut to nine** (G-ritual
  leads; G-shape retired done; G-workbench parked; G-onboard + G-trial
  moved to beta) · cadence = daily autonomous lanes + one digest/day to
  the portal (`worlds/daily-digest/<date>`) · time-off pace. Approved
  with four refinements: (1) the ritual is the **daily home loop**
  (orient · remember · resume · discover), not morning-exclusive;
  (2) the Projects ruling above; (3) G-fast measurement definitions ship
  as code with the gate, and the **Vault-portability decision must close
  before G-recover may claim green**; (4) append-only decision history
  preserved — TRUE-NORTH owns direction only; ADRs + contracts retain
  their own authority. Owner philosophy recorded verbatim in TRUE-NORTH:
  "Worlds should help you recover your place in your own life."
  Supersedes: the 2026-09-21 delivery plan (banner added; historical),
  and the finish line + ROADMAP **as direction** (banners added; bodies
  kept as detail). Reason: 16 days of sprawl accreted around the founding
  idea ("the companion IS the world"); the owner re-centered the product
  on one daily loop before any scope expansion ("I want to experience the
  actual daily loop before we expand scope again").

## Wave 1 execution + live deploy — 2026-09-22 (evening)

- **2026-09-22 — Wave 1 landed; live instance and portal fix deployed
  (owner taps: "Deploy + verify now", "Update live now").** Three lanes
  merged serially with full gates (A home loop `b17431b` · B one voice
  `6fb73d5` · C Memory deep `944a59f`) + orchestrator fix `41a5dcf` —
  which caught a real product bug at merge: the thread card read
  `events[0]` of `GET /api/journal`, newest-first only against the e2e
  mock; the real backend answers oldest→newest. The card now reads the
  server's own `GET /api/journal/last` (API-084); the client never picks.
  The CI red that exposed it was a fixture leak (the journal-draft suite
  publishing into the shared mock journal) — fixed with a test-only reset
  route + adverse-order proof, assertion unchanged, no gate weakened.
  Live instance: image built from `41a5dcf`, recreated with the item-4
  `config-data` volume, `world-data` intact, `/api/journal/last`
  404→401; rollback tag `personal-world:pre-wave1` kept; runbook in
  `docs/OPERATIONS.md`. Portal: the wpub dir-mode defect (directory
  rename needs write on the directory itself) fixed in homelab PR #45
  (dirs born 2775), deployed owner-approved, verified by a sudo-free
  publish→approve→promote round-trip; evidence appended to the PR.
  Security flag: the live `PW_API_TOKEN` value appeared once in session
  diagnostics before filtering — in no tracked file; rotation offered,
  owner's call (value never restated anywhere). Compose quirk recorded
  in `docs/OPERATIONS.md`: locally-built images need `up --pull never`
  (Compose v5.5.1 + buildx docker-container driver tries the registry
  first and fails `denied`). Reason: honest record of everything that
  changed live state tonight.

## Vision review + Step 1 "first light" — 2026-09-25

- **2026-09-25 — Vision review; `.project/PLAN.md` becomes the plan
  (owner-approved).** Owner answers: things come to her (email-like, calm,
  have-tos in one place); the bridge of her station (Constellation star map
  as starting direction); Worlds + Project Home are one product in her mind;
  fun is a requirement. Supersedes TRUE-NORTH scope and sequencing where they
  differ; its honesty and accessibility principles stand. Parked:
  Node/Headscale, Workbench, new contract machinery. Reason: the owner's own
  statement of intent, recorded in the review doc and PLAN.md.
- **2026-09-25 — Keeper, briefing and bridge are one experience; personality
  in 1b (owner directive).** Each system has a resident from the owner's
  canon who reports it in their own voice (Bolt: Workshop/agents; Hekek:
  Engine room/estate; Bruma: Archive/records; Mira: Observatory/interests;
  Burrito Journalism: Newsstand; Ratatoskr: World tree/threads). The World
  Keeper speaks the briefing in words; its artwork never encodes status (the
  WORLD_KEEPER founding rule stands). Reason: "personality should influence
  how information is presented and explored, not just decorate."
- **2026-09-25 — Default theme plain → starfield (supersedes D2 of
  2026-09-22).** Owner directive: the warm sci-fi identity; calm does not
  mean boring. Reversible: Settings still offers every theme; device choice
  overrides. Reason: owner directive, PLAN.md rule set.
- **2026-09-25 — `ui/` truth pass: unused API hooks are unfinished intent,
  not dead code.** Only the orphaned `ui/src/mocks/server.ts` and
  placeholder copy were removed; media/reminder/connection hooks stay for
  wiring. Reason: owner rule "distinguish dead code from unfinished product
  intent".
- **2026-09-25 — Personality pack ON by default (supersedes the 2026-09-22
  "off by default" routing).** Owner, in the Doorways design session: "turn it
  on", everywhere, not only with the Doorways theme. `personality_pack`
  now defaults to `residents`; `off` stays one choice away in Settings and
  remains the fail-safe for missing or malformed values. The honesty and
  accessibility floors are unchanged, and residents' artwork still never
  encodes status. Reason: PLAN.md 1b ("personality ships here, not later")
  and the owner's note that the residents are now much less obtrusive.
- **2026-09-25 — Sol has no voice; a plain Assistant is the default
  companion.** Owner: Sol "is a bigger thing with no real voice", present
  in menus and little moments, and "we should make a super generic
  assistant if you haven't picked one, maybe just a computer screen face".
  `companion` now defaults to `assistant` (persona template
  `config/prompts/personas/assistant.md`, art `design/assets/crew/assistant/`);
  `personal-world` (Sol) stays in the vocabulary but never becomes a chat
  persona (`voice.VOICELESS_COMPANIONS`). Open question for the owner: the
  Bridge briefing's "Keeper" line still uses the `personal-world` resident.
- **2026-09-26 — Crew page, Mira keeps Studio, commbadge placeholder; the
  Assistant is "no companion".** Owner, answering the design handoff's open
  decisions: "Mira for the Studio, a new Crew page that links from settings,
  and … the commbadge logo". (1) Mira keeps Studio (landed separately in #83, `crew.ROOM_RESIDENT`). (2) The crew
  manager is its own page reached from Settings, not a nav landmark; the
  skeleton stays Overview · Memory · Chat · Settings. (3) A companion with
  no picture wears the crew commbadge (Sol's ringed planet) with their
  initial. (4) Since #81 the server maps the old `assistant` value to
  `companion_id: null`, the one plain voice, so the frontend shows that
  plain voice as the Assistant (screen face) instead of adding a crew
  entry; Settings now edits `companion_id` from the person's crew and
  retires the old `companion` row, which stopped changing the voice once
  `companion_id` was stored. `config/prompts/personas/assistant.md` is no
  longer composed by the voice path. Reason: owner canon, "an assistant if
  you haven't picked one", and one resolution for face and voice.
- **2026-09-26 — A shared doorway and face library, chosen, never assigned.**
  Owner commissioned 12 room doorways and 16 portrait-only faces
  (`design/assets/library/`) so other people's Worlds have art too. Owner:
  "let people select things" and "no need to set defaults": a room shows the
  doorway chosen for it on the Crew page, else its own painted interior, else
  the plain arch; a face from the library becomes a companion's own picture.
  The doorway choice is device-local for now (like the theme) until the
  station has somewhere to keep it. Reason: owner direction; art never
  implies a fact about a room.
- **2026-09-26 — Doorway choices move to the station; the Bridge credits the
  plain voice to Worlds.** With #86 live, a room's doorway is read from and
  written to the server (`doorway` on each room row, PUT
  /api/rooms/{id}/doorway), so it follows the person across devices; the
  device-local store is removed. With #88 live, the Bridge shows Sol's small
  mark beside Worlds' plain voice (crew off) and the commbadge for a chosen
  companion with no picture; Sol never speaks. Studio has no default keeper
  (owner nixed it, #85).
- **2026-09-26 — First Light is the real /setup wizard.** Owner: "yes". The
  server-rendered wizard now follows the First Light design: six steps
  (welcome with the bridge portal and Sol, getting ready, sign-in, comfort,
  companion, welcome aboard). Comfort adds colours (Starfield default,
  Doorways, Plain; previewed live, saved on this device under the key the
  app reads) and "Meet the crew" (`crew_on`, #89). The companion step offers
  the Assistant (default, the plain voice) and the starter crew
  (`/api/setup-wizard/crew`, `/api/setup-wizard/companion`), and steps aside
  when the crew is off. Every safeguard is unchanged: loopback-only writes,
  first-run only, the same provisioning, sign-in and finish code. No
  motion: the progress dots and the lamp are static.
- **2026-09-26 — The Bridge's first day, and the name is "Worlds".** Owner
  approved the FirstBridge board: a first-day guide on the Bridge, spoken by
  the chosen companion (Worlds' plain voice with Sol's mark when the crew is
  off), with four live lines (first room, systems answering, first note —
  a journal entry the person wrote — and a chosen companion). It hides when
  put away (this device) or when everything is done; Settings brings it
  back. Rooms get a plain in-app explainer (owner: "probably a plain
  explainer"). The overall status says unreachable systems as a count ("1
  system can't be reached") rather than a lone "Unavailable". Owner: "just
  call it worlds, I like it better" — the header, footer and tab title say
  Worlds.
- **2026-09-26 — Sol's little moments, and the type floor in every theme.**
  Owner: "start on everything". Sol (the voiceless Worlds mark) now appears
  as the header logo and in small, static, decorative moments beside
  Worlds' own words: curious while the Bridge gathers, resting when it
  can't reach the world and on a quiet day in Rooms, and cheering once in
  "You're all settled in" when the first-day guide is finished (only on a
  device that showed the guide, so an already-settled World is never
  surprised). Full cutouts only, never the peeking hello crop, never
  animated, always aria-hidden. Every theme now meets the type floor (body
  ≥16px, labels ≥13px; #101, #104).
- **2026-09-26 — Chat, Memory and Settings in the Doorways look; companion
  messages.** Owner approved the boards (Doorways-Chat,
  Doorways-MemorySettings, Companion-Messages). Chat says who answers ("Chat
  with Renai", or "Chat with Worlds" with the crew off), with the
  companion's face beside their messages, a static "… is thinking", a
  visible Message label and the provider under Technical detail; the list is
  the one live region. Settings leads with your crew (face and name), serif
  section headings, theme swatches drawn from each theme's own tokens, and a
  "Companion messages" choice. Memory gets serif headings and, in the
  Doorways theme, the archive doorway. Companion messages: one line on the
  Bridge only when something arrived or needs you, at most one every 30
  seconds (newer news waits and is batched), dismissible, silent on quiet
  days and while the first-day guide speaks; device-local setting: when
  something happens · only when something needs me · off.

## 2026-09-26 — Daylight, a light theme pack (owner approved)

The owner approved the "Theme · a light option" board ("love them all").
Daylight is an optional pack (`design/themes/daylight.json`); dark stays the
default. Warm paper (#f4efe6), never white; text #2a2433; links, focus and
primary buttons in a deep amber (#8a4f0f) with cream labels, because labels
use `surface.void`. Every text and accent colour passes 4.5:1 on every
surface (worst 4.7:1). The starry backdrop is hidden in Daylight, native
controls follow it (`color-scheme: light`), and WorldSignal's rank dots use
dark ink at the same strengths, so rank is still encoded by contrast alone.

## 2026-09-29 — OpenBao re-opened; Candy scope; the API-only routes (owner decisions)

- **OpenBao.** The owner is happy to re-open OpenBao and migrate to it.
  ADR-0007 is now accepted; the migration plan is still pending. This
  replaces the earlier record, which said "approved 2026-09-26" in one
  place and "proposed, not accepted" in another.
- **Candy scope.** Candy is intended to be only the backend for the
  Interests category (discovery). It is not implemented quite right yet.
  Media, calendars and notifications are out of Candy's scope.
- **API-only routes.** `/api/lab/*`, `/api/exports/story` and
  `/api/reconciler/status` have no screen on purpose. They stay as the
  intentional API-only "Lego box" contract (see `docs/ARCHITECTURE.md`).

## 2026-10-01 — Front-door rebuild approved (ADR-0008)

Owner approved PR #231 (head dbc1218) with refinements in `HANDOFF-FRONT-DOOR-APPROVAL-2026-10-01.md`: clean rebuild authorized; authority and durable single dispatch before any side effect (including Connect test/run); Worlds asks the owner directly for actions on services Project Home does not govern and keeps bindings and receipts; Memory durable from day one; Chat optional; landmarks `Home · Connect · Memory · Settings`. Recorded as `docs/adr/0008-front-door.md` (accepted, amends ADR-0001), with dated supersession notes on S1–S10 sources. Archive tag `archive/pre-front-door` preserves the last pre-rebuild source (61397e0, which is also the commit production runs).

## 2026-10-01 — Rebuild: start fresh, private notes in SOPS, stack kept

Owner answers after S0: **old Worlds data is not imported.** The old journal, `world.json`, stickers and search index stay in the private backups and the old data dir until retirement; no migration code is built. Private reconstruction notes get a SOPS-encrypted permanent home in the owner's private operator docs (location being established; plaintext is never committed). The orchestrator kept the stack (Python/FastAPI/uv, React/Vite/TypeScript/react-query) and set the five rebuild contracts in `docs/rebuild/CONTRACTS.md`; obsolete modules are deleted on `rebuild/front-door`, not adapted.

## 2026-10-02 — Home order for Calm and phones: the bad-day layout (owner approved)

Rylee approved two changes to the Home order in the approval handoff (§8), after an accessibility and "bad day" audit of the merged front door. They amend that order for Calm density and for phones; Standard and Detailed on a wide screen keep the original order.

- **D1.** Calm is the bad-day layout: greeting and briefing, then **Needs you first**, then a condensed strip, Needs a look, Your life, and Quietly working folded to one line.
- **D2.** Condensed strip, in Calm at every width and on phones (under 760px) in every density: only the sources that need a look, plus one tile "● N quiet" that opens the full strip in place (`aria-expanded`, focus stays on it). Healthy and not-configured sources fold into that tile. No wall of green.

Why: a tired person should meet what needs them before nine tiles. How to apply: keep Needs you directly after the briefing in Calm; never make the condensed strip the only way to reach a source (the quiet tile always opens the rest).

Also decided in the same pass (owner may veto): the Plain theme is removed (it matched Starfield); a state has one word everywhere (badges, strip, briefing, accessible names); no control that does nothing is shown (the disabled Approve and the Memory Records and search placeholders are gone until they work).

## 2026-10-12 — Default theme starfield → Mulberry & Mint (estate base)

Rylee made the World Tree Field Guide's Mulberry & Mint palette the shared base for every app (design-system `tokens/mulberry-mint.tokens.json`, its package since design-system #50/#56) and chose to switch Worlds too. The front door's `:root` colours are now Mulberry & Mint dark; Starfield and Daylight stay in Settings → Theme. A save from before the switch with `theme: "starfield"` and no `themeV` opens in Mulberry & Mint, because Starfield was only ever the default there; a Starfield picked after the switch is kept. Mint is the one primary action and the selected state, so the "needs" band and the Needs-a-look stripe use the warm `--warn` colour (apricot here, near-identical to the old gold in Starfield). The focus ring stays the accessibility contract's teal `#72b1b1` (tests/test_design_tokens.py). Supersedes "Default theme plain → starfield" (2026-09-25). Reversible: change `:root` back and the default in `prefs-core.ts`.
