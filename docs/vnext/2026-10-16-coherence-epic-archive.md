# Legacy Worlds coherence epic | exact issue-body snapshot

**Original:** https://github.com/rylee-bee-labs/worlds/issues/312

**Title:** Epic: Worlds front-door coherence, human acceptance and safe cutover readiness

> Copied verbatim from the source issue on 2026-10-16. The original discussion/comments remain at the linked GitHub issue. The purpose is to keep all unique historical constraints readable even if this duplicate *parent* tracker closes as superseded.

---

> **LATEST OWNER DIRECTION · 2026-10-13:** Cleanup remains first, **and** Worlds vNext now explicitly includes a **new visual design [#322](https://github.com/rylee-bee-labs/worlds/issues/322)** plus a **new Connect API [#323](https://github.com/rylee-bee-labs/worlds/issues/323)** in the same gated campaign under [#321](https://github.com/rylee-bee-labs/worlds/issues/321). Earlier “design on hold” statements are superseded. No implementation of unapproved mockups, API trust changes or deployment; first preserve and clean, then design/contract gates, then build.

## Why
2026-10-13 **Worlds coherence and readiness audit**. The front door (Home · Connect · Memory · Settings) is **source merged to main** (PR #277, 2026-10-06); actual deployed runtime revision remains **UNKNOWN** without private `/healthz` proof. GitHub open issue queue was empty at discovery because 2026-10-07 retirement moved unfinished work to `docs/BACKLOG.md`. Optimize existing capabilities and historical work rather than building a third experience.

## Verified source facts
- `src/personal_world/worlds/production.py` assembles owner auth, action dispatcher, Memory, room/0, Companion proxy, Connect and static front door.
- `ui/src/fd/{Home,Connect,Memory,Settings}.tsx` implement the four landmarks; `FdApp.tsx` mounts Companion. `ui/src/fd/Settings.tsx` still labels Assistant 'Not installed' (needs honest capability check).
- `ui/src/fd/types.ts` still defines handwritten API models despite generated `ui/src/generated/api-types.ts`; `scripts/gen-openapi.py` and `scripts/contract-drift-check.py` already exist. Do not duplicate them.
- `docs/accessibility/FRONT-DOOR-SCREEN-READER-WALKTHROUGH.md` explicitly says the **human** walkthrough has not been run, though automated Playwright checks exist.
- `.project/CURRENT.md` has correct source cutover status; `AGENTS.md`, `.project/PLAN.md`, `docs/INDEX.md`, `ui/README.md`, `docs/QUICKSTART.md`, `SECURITY.md` contain stale/contradictory route, branch, install or schema guidance. Contracts and historical provenance must stay intact.
- [#262](https://github.com/rylee-bee-labs/worlds/issues/262) captures unfinished Phase 4/source readiness work. [#267](https://github.com/rylee-bee-labs/worlds/issues/267) captures **proposed** Play-Nice semantic-kernel work; only a vocabulary/deletion inventory is justified first.
- [#268](https://github.com/rylee-bee-labs/worlds/issues/268) describes old Studio kit drift. Studio's [#29](https://github.com/rylee-bee-labs/studio/issues/29) changes the source-of-truth strategy toward the separate shared design-system tokens; do not blindly re-stamp its vendored copy.

## Contract guardrails
- Preserve the approved ADR-0008 four landmarks, human-language front door, one authority path and Project Home's authority for its own consequential operations.
- No deploy, external exposure, migration, DNS, identity-provider change, token/grant generation or destructive retirement authorized by this issue.
- Zero-provider and zero-model modes remain useful; no fake data or green when state is unknown.
- Human reliability and the accessibility floor are architectural requirements; real-device + assistive-technology tests cannot be replaced by mock/Chromium-only success.
- This is a **public repo**: only synthetic evidence and generic paths may enter issue comments/PRs. Secrets, private hostnames/topology and personal data go only to owner-controlled private operator logs.
- Keep approved artwork, companion character canon, rollback/old-runtime artifacts and durable memory protected until explicit owner decision.

## Delivery order
1. Map present code, routes, tests, branch and source vs private running revision (**no deployment**).
2. Reconcile retired-source leftovers and canonical docs; check the release/operator paths.
3. Prove front-door use with real-provider, keyboard/screen-reader and phone paths.
4. Reconcile Companion and UI state truth, Memory durability and at-most-once action receipts.
5. Perform #267's **Packet A only** after current-code inventory; decide on ADR-0009 before any semantic refactor.
6. Classify Studio kit/design-system relationship by current consumer rather than old docs.

## Done when
Each verified gap is closed by a small PR, test and source evidence; the human-facing frontend is genuinely usable; deployed runtime remains explicit UNKNOWN until safely checked; owner approval remains required for production. Add links to tracked child tickets below as they are created.

## Linked queue and acceptance sequence (2026-10-13)

### Now: source truth and human proof
- [ ] [#313](https://github.com/rylee-bee-labs/worlds/issues/313) — current install/source/route/doc index truth. P0; do not copy old Station/Bridge guidance as live product.
- [ ] [#314](https://github.com/rylee-bee-labs/worlds/issues/314) — real screen-reader, real-phone and keyboard accessibility walkthrough, explicitly NOT RUN until performed.
- [ ] [#315](https://github.com/rylee-bee-labs/worlds/issues/315) — honest Home observations and useful Needs you on zero-provider/room/0/failing-provider cases; private provider runtime tests remain separate UNKNOWN.

### Close the coherence seams; preserve current code
- [ ] [#316](https://github.com/rylee-bee-labs/worlds/issues/316) — verify misleading Settings 'Assistant: Not installed' vs currently mounted, governed Companion and its actual configured states.
- [ ] [#317](https://github.com/rylee-bee-labs/worlds/issues/317) — audit generated OpenAPI vs handwritten fd types and prove existing drift check. Proposed #267 kernel refactor must not start from a guess.
- [ ] [#318](https://github.com/rylee-bee-labs/worlds/issues/318) — Station/theme-pack placeholder, product theme ownership and design-system consumers. Visual owner gate; not a second Studio.

### Historical work brought forward deliberately
- [ ] [#262](https://github.com/rylee-bee-labs/worlds/issues/262) — **reopened** for verified Phase 4 residual *source/test/rollback readiness*, not pre-Oct6 branch merge or production cutover.
- [ ] [#267](https://github.com/rylee-bee-labs/worlds/issues/267) — **reopened for Packet A inventory only**; ADR-0009 still proposed. No semantic refactor without owner architecture review.
- [x] [#263](https://github.com/rylee-bee-labs/worlds/issues/263) — pre-cutover main/rebuild reconciliation; completed/superseded by PR #276/#277, remains closed and annotated.
- [x] [#268](https://github.com/rylee-bee-labs/worlds/issues/268) — old Worlds kit/Studio re-stamp direction; remains closed and annotated because canonical design-system ownership strategy changed. Studio [#29](https://github.com/rylee-bee-labs/studio/issues/29) preserved as separate history/consumer gate.

## Explicit "do not conflate" list
- Merged **source** is not a deployed running front door. Deployed state remains UNKNOWN until private `/healthz`/operator proof.
- Automated Chromium/axe tests are not a human screen-reader or physical phone pass.
- Local `home` cards with synthetic providers are not proof of live integrations.
- A Play-Nice kernel **proposal** is not an accepted ADR or authorization for destructive refactoring.
- Old kit copies are not canonical shared design tokens after Studio/design-system decisions.
- Owner review controls deploys, private state migration, consequential provider action authority, character/canon/art and any external publication.
- Do not include real instance topology, hostname, credentials, logs or personal Memory in public issues/PRs.

## Coordination
Each child issue should produce focused code/test or evidence updates with the latest `main` SHA, clearly separated `PASS | FAIL | N/A | UNKNOWN`, and a reviewable PR. Keep the contract floor intact: accessibility, human reliability, privacy, one action authority path, and durable Memory. Close this epic only once those acceptance claims have *verified evidence*; a tidy issue list is not itself a source/runtime gate.

## External-first architecture correction (2026-10-13)
- [ ] [#319](https://github.com/rylee-bee-labs/worlds/issues/319) — **architecture acceptance prerequisite**: verify ownership per subsystem against the approved **universal dashboard / front door**, not only internal consistency. Worlds owns meanings and accessible composition; Project Home, agents, Companion, repos and external services own their mechanics and source truth. Owner-approved local deterministic Memory remains a narrow core exception. Require a third-party adapter onboarding proof before expanding internal domains.
- Treat [#262](https://github.com/rylee-bee-labs/worlds/issues/262) and [#267](https://github.com/rylee-bee-labs/worlds/issues/267) as contingent on #319's classification. A tidy semantic kernel that still duplicates external systems is not success.

### Critical missing user-facing universal-connection seam (2026-10-13)
- [ ] [#320](https://github.com/rylee-bee-labs/worlds/issues/320) — **P1 after ownership inventory / parallel UI-ready work:** connect the existing recipe CLI/backend into Connect's currently placeholder Recipes tab; prove one new HTTP service and one room/0 provider can become usable Home information without a new internal domain. Include backend/frontend auth-mode parity without exposing secret values. This is an actual current UI capability gap, not a request for new machinery.


## Owner product-direction correction (2026-10-13)
Rylee explicitly wants **a brand-new Worlds design and a new API Connect layer**, delivered via the estate's **new gated jobs** process. [Worlds vNext design mission #321](https://github.com/rylee-bee-labs/worlds/issues/321) now governs product direction. This epic's existing #313–#320 work becomes **current-code discovery, guardrails and candidate implementation**, not automatic architecture or UI instructions. Do not start the prior four-landmark FdApp polish/old Connect wiring campaign as if visual direction were approved. Owner design pick and Connect contract review come first; retain all security, accessibility, Memory preservation and external authority constraints.

## Cleanup-first execution order (owner clarification 2026-10-13)
1. **Inventory and preserve**: record exact `main` baseline, references/consumers, test/CI gates, old-runtime backup/rollback handles, no production assumption. Establish keep/replace/retire/unknown evidence (no delete from name alone).
2. **Source & documentation hygiene**: [#313](https://github.com/rylee-bee-labs/worlds/issues/313), [#262](https://github.com/rylee-bee-labs/worlds/issues/262). Repair known stale facts, remove proven orphaned old routes/modules/tests in small independent reviewable PRs, preserve needed histories/contracts.
3. **Duplication/ownership audit**: [#317](https://github.com/rylee-bee-labs/worlds/issues/317) and [#319](https://github.com/rylee-bee-labs/worlds/issues/319), **read-only mapping first**. Eliminate only objectively redundant code/data with source-based consumer proof. Existing runtime behavior and external authority stay unchanged.
4. **Prove clean baseline**: frontend/backend build, lint/tests, CI/security, API/drift, accessibility *automated* gates, zero-provider and Memory restore/action at-most-once regression. Separate any unavailable live, screen-reader or device result as UNKNOWN and queue for later acceptance.
5. **Stop and hand back**: concise cleanup ledger: kept/retired/unknown, verified tests, outstanding blockers, risk and preservation/rollback, and question whether to move to design. No unsolicited prototype.
**Do not start** #320 recipe UX, #267 semantic implementation, or #321 design while cleanup runs; their findings may guide safe preservation but not enlarge current scope.

### vNext now explicitly includes new design and API (latest owner update)
- [ ] [#321](https://github.com/rylee-bee-labs/worlds/issues/321) governs the complete cleanup → design/API → prototype → verified build campaign.
- [ ] [#322](https://github.com/rylee-bee-labs/worlds/issues/322) genuinely new phone/desktop visual design; Rylee's design gate.
- [ ] [#323](https://github.com/rylee-bee-labs/worlds/issues/323) new universal Connect API contract and proof; authorization/security/owner gate.
This epic's cleanup issues are now **stage 0**, not a reason to omit visuals/API. Do not launch prototype before the relevant gates.

