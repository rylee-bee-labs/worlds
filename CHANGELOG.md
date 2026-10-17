# Changelog

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the curated milestone record · **Read this if:** you want to know when something landed and why.

**In short:** the big moments, newest first, one line each with the PR. It
is a record, not today's state: for that read `.project/CURRENT.md` or, in
plain words, `docs/WHERE-WE-ARE.md`.

## [Unreleased]
- 2026-10-15 — **One Companion, one name (#316).** Settings reported an unconditional "Assistant: Not installed" — a leftover from the deleted Station *World Assistant* drawer — while the governed Companion was mounted and working. Settings now has a "Companion" section that reads the same `GET /api/companion/health` as the panel, words it identically (up / not answering / not set up / unknown / not the owner), adds the next step, and opens that same panel. One read, no thread, context or grant; approvals still live in Project Home. Meaning documented in `docs/COMPANION.md`; tests in `ui/src/test/fd-settings.test.tsx`.
- 2026-09-26 — **Docs truth pass + screenshot gallery.** Every page carries a status line (Current, Reference, Direction, Historical) and a plain-words summary; README, WHERE-WE-ARE, ARCHITECTURE, OPERATIONS and COMPANION-CANON match the verified state; new `docs/ROOMS.md`; `docs/gallery/` captures every screen at 390/1440 from the mock API.
- 2026-09-26 — **Per-person rooms (#103).** Rooms that opt in (`forward_principal`) are told who is asking with `X-Worlds-Principal` alongside their own token; cards and needs are cached per person. Candy is the first. Engine room and Candy are live in production.
- 2026-09-26 — **Type floor in every theme (#101, #104).** Body text 16px, labels 13px, in starfield, doorways, station, moss, ocean and plain.
- 2026-09-26 — **Secrets in the Workshop drawer (#96, #98, #100).** Read-only, admin-only: station health, key names, pending requests and recent changes in Project Home's own words. Never a value.
- 2026-09-26 — **The Worlds kit (#97, #99).** The design language exported as framework-free `ui/dist-kit/` (tokens, `wk-` components, fonts, preview), with drift and accessibility gates in CI; Studio, Project Home and Candy vendor it.
- 2026-09-26 — **Rooms open on their own site (#95).** Review a need on the room's own site in a new tab and come back to the exact item; rooms may publish a browser `public_url`. No proxy.
- 2026-09-25 — **Runtime room registry (#87).** The room list comes from Project Home at runtime, with last-known-good and an `incompatible` state for unsupported contracts; `token_env` restricted to `PW_ROOM_*_TOKEN`.
- 2026-09-25 — **Crew, keepers and doorways (#80, #81, #85, #86, #88, #89).** Per-person starter crew, a chosen companion (or the plain Assistant), a keeper and a doorway per room, and First Light's crew and companion steps.
- 2026-09-25 — **The Bridge is home (#68).** Keeper, briefing and rooms as one experience, fed by real Project Home, lab and journal data.
- 2026-09-23 — **Docs/CI/skills truth pass (post-flip + post-Wave-1).** The public face and the agent map caught up with reality: the README no longer sells the retired star-map Station as the product (calm hub `Overview · Memory · Chat · Settings`; honest per-surface wiring incl. live `GET /api/journal/last`, device-local chat with real replies when a model is configured, labelled specimen surfaces), provider/template counts corrected to the code (10 native providers — `native_git` never existed; 21 brain templates since the persona pack), the implement-figma skill's whole map re-pointed from the deleted `frontend/` tree to `ui/` (token pipeline → `ui/src/generated/`, vitest+Playwright layout, fixture-API recipe with the mock journal-ordering quirk recorded), `ARCHITECTURE`'s `/station` section rewritten for the redirect-only era, and the validate workflow's stale "no frontend build stage" step name fixed. Station-era docs and handoffs carry snapshot banners; the Crew & Station thesis is amended in role (crew/voice truths canonical; Station-as-experience superseded); INDEX statuses aligned. Gates: pytest RC=0 · framework validate clean. *(Summary entry — compiled from git log 2026-09-23.)*
- 2026-09-22 — **TRUE-NORTH re-vision + Wave 1 landed; live instance updated.** A three-round owner interview after a 24-product research pass made `docs/TRUE-NORTH.md` the canonical direction (`2527c0d`): the calm hub, the daily home loop (orient · remember · resume · discover), one voice with selectable tone registers, residents → optional pack, skeleton-only scope + one discovery sliver, alpha gates recut to nine; finish line, ROADMAP, and the delivery plan carry superseded banners. Wave 1 merged serially — home loop in Overview (`b17431b`), voice unification (`6fb73d5`), Memory deep with models-off proof + `GET /api/journal/last` (`944a59f`) — and the merge fix (`41a5dcf`) caught a real product bug: the thread card trusted the mock's newest-first journal order (real backend: oldest→newest); it now reads the server's own `/api/journal/last`. CI all-green; the live :8000 instance was updated to `41a5dcf` with the item-4 `config-data` volume (rollback tag kept; runtime proof `/api/journal/last` 404→401). Estate: the Station Workshop portal's approve-path defect (wpub dirs born 755; directory rename needs write on the directory itself) was fixed in homelab PR #45, deployed owner-approved, and verified by a sudo-free publish→approve→promote round-trip; the daily-digest cadence to the portal is live (`worlds/daily-digest`). *(Summary entry — compiled from git log 2026-09-22.)*
- 2026-09-22 — **The flip: the React rebuild IS the interface.** `/` serves the production build auth-gated; `/station*` + `/vnext*` 307 → `/`; the vanilla Station and the old `frontend/` suite were deleted from the tree; the Dockerfile's node stage builds `ui/` into the image with a build-time existence assertion; `plain` became the first-release default theme (teal primary, amber rare highlight, Young Serif headings; starfield demoted to optional pack) (`d5f16a3`, `b7e07fc`, `e08ce5c`); the setup wizard pauses on blocking warnings and says "Worlds" (`6ec45e6`); compose persists `/config` in a named volume (`740432c`). *(Summary entry — compiled from git log 2026-09-22.)*
- 2026-09-20 — **Untracked `.fossil/cache.json`** (owner call: untrack). 3 MB disposable analysis cache with machine-absolute paths, referenced by no tooling; public-safety test was its last honest witness. `.fossil/` now gitignored.
- 2026-09-20 — **build-vnext.sh parameterized (pre-existing hygiene red).** tests/test_public_safety.py flagged a a hardcoded personal home-directory default; now `VNEXT_SOURCE` is required and fails closed. Remaining known red: `.fossil/cache.json` (tracked cache with absolute paths — owner decision pending: untrack vs scrub), and rylee_lore's pre-existing deterministic-test reds.
- 2026-09-20 — **Play-Nice re-pin.** Upstream library rewrote commit metadata to remove personal identifiers (content unchanged); our pinned SHA retired. Repinned to `a0e3efb`; adopt VALID (always=11 triggers=9).
- 2026-09-20 — **Station vNext mounted side-by-side at `/vnext/`.** The React vNext build is served at `/vnext/` behind the same auth gate while the production vanilla Station at `/station/` stays live (`0d249c5`); a frontend-inventory report documents the five stacks in flight and what each needs (`56d76f8`). *(Summary entry — compiled from git log 2026-09-20, not a curated milestone.)*
- 2026-09-19 — **Content DB tool provider.** The generated content index ships as a tool provider (`9f34b7b`); `data/content.db` is gitignored as generated output (`fd1e256`). *(Summary entry — compiled from git log.)*
- 2026-09-18 — **"One world, eight dialects" canon + Today design-study day.** Station map records the eight-dialect principle (`7532989`), deck names re-anchored to plain job words with Records replacing Backups (`0c5b4e3`, `6b9d37c`), three area residents canon'd (Hekek, Bruma, Mira) with the deck map (`6c4caba`); ~15 Today-room design studies (focus layer, holographic avatars, need-first alerts, portable-display cards); pronoun canon recorded as owner-stated (`1990a32`); atlas-deep resume card lands (`e232dc8`). *(Summary entry — compiled from git log.)*
- 2026-09-17 — **Full language & truthfulness pass complete.** LANG-001…LANG-060: product identity fixed to **Project Worlds** (`e14bf56`), human-first default copy with technical detail split (`e893205`), delete-scope / Vault-boundary / storage-failure truthfulness (`5d79421`), chat send wired to the real `POST /api/chat` with honest states (`20169d0`), preference-authority scope labels (`e2f2517`); pass closed with reconciliation (`96d5f92`). Same day: canonical Character Handbook + companion canon (`5d24493`, `155dcd4`), Station art set curated from the owner drop (`7db1383`), alpha remediation reconciled with the hardening wave (`b459cbc`). *(Summary entry — compiled from git log.)*
- 2026-09-16 — **Station-only cutover.** `feat(serve)!`: the React SPA is dropped and `/login` is served server-side (`f4c735a`); docs remove React-frontend references (`0686285`) and record the single-branch consolidation (`72d4665`). Also: passkey-first sign-in with SSO primary (`0e01785`), fail-closed step-up + loopback-guarded setup writes + session-file hardening (`0f71e03`, `193e47d`), public-safety gate extended to every tracked text file (`1fe5053`), operator topology retired from public current-state docs (`fd36548`), deterministic Station capture + README gallery (`de62beb`). *(Summary entry — compiled from git log.)*
- 2026-09-15 — **Backlog + governance day.** Due reminders now deliver through native notifications (`eb61482`), journal e2e test race fixed (`8a35bc9`), canonical project-estate vocabulary for Projects (`a36939a`), participant packs normalized to participant-v1 (`b836c5e`), Play Nice re-pinned to v0.7.0 with re-attestation (`c4283bc`). *(Summary entry — compiled from git log.)*
- 2026-09-13 — **Workshop v3 complete: all 16/16 frames implemented.** The remaining 10 canonical frames landed in a single parallelized run (`6d909cc`): Interests (warm empty state), Journal Writing (focused notebook composer), Journal Reading ("Your words, kept safe"), Bad Day (three-tier triage), Notifications (good-news/small-update/action-required pattern), Companion Popover (progressive disclosure rest→focus→open), World (capabilities as senses), Settings (two-column grid, companion cards), Setup (two-panel greeting), Projects (card-based layout). All implemented from local Figma evidence (design context + screenshots + metadata captured via bridge). Gate: 647 backend / 371 frontend / tokens:check / lint / build / framework validate (0 violations). D4: PENDING_BUNDLED_UAT.
- 2026-09-13 — **Workshop v3 batch: Vault, Login, Chat implemented; 6/16 frames done.** Three more canonical frames landed: **Vault** (`600c3e4`: 17:1014, container metaphor with lock/unlock, treasure listings, sea-charm companion warmth), **Login** (`02f6ee5`: 17:1681, pre-auth companion greeting, "Enter" literal, no nav), **Chat** (`91560ff`: 17:2536, companion-present conversation, message bubbles, thinking state, send interaction). All implemented from fresh live MCP evidence (bridge restored mid-run). New tokens: `surface.raised`, `border.strong`, `accent.primary_bright`, `accent.gold`, plus warmth-specific vault/login/chat tokens (T5 hex gate enforced throughout). Owner reservations: chat send button 36px vs 44px floor (floor won), login key icon (no canonical glyph), chat presence/thinking wording. Gate: 600 backend / 363 frontend / 43 e2e / tokens / lint / build. D4: PENDING_BUNDLED_UAT.
- 2026-09-13 — **Figma bridge finding: `get_design_context` requires frame selection.** Unlike `get_metadata`/`get_screenshot` (which accept `nodeId` without selection), `get_design_context` returns `"Nothing is selected"` if no frame is active in Figma Dev Mode. Documented in `.project/CURRENT.md` and the implementation skill. Previously undocumented; discovered during multi-frame run when bridge was healthy for metadata/screenshots but silently failed for design context.
- 2026-09-13 — **Workshop v3 multi-frame run: Question (17:6245) and Mobile Today (17:1929) implemented; 3/16 frames done.** A rolling implementation run landed two more canonical frames — **Question** (`f3be17a`: uncertainty-shaped attention renders the curious-companion question region from REAL capability-`unknown` data, canonical framing lines verbatim, Level-4 evidence disclosure; mixed attention keeps the restrained list) and **Mobile Today** (`b88f633`: the ≤599px phone composition of the Quiet Day — greeting band, compact health pill, avatar quiet message, icon-frame change rows, rose journal entries — with three new canonical warmth tokens entering `design/tokens.json` first). Both implemented from preserved canonical evidence (complete cached `get_design_context` + reference screenshots from the live bridge earlier on 2026-09-13) because the Figma bridge went down mid-run; the remaining 13 frames are blocked on fresh MCP retrieval (tracked in #37). Owner reservations (companion presence scale, waves/waterline placement, mobile-nav item count) accumulate evidence but remain undecided. Full gate at the frozen commit: 600 backend / 363 frontend / 43 e2e / tokens / lint / framework validate / build. D4 for all implemented frames: PENDING_BUNDLED_UAT.
- 2026-09-13 — **Workshop v3 implementation era begins; Today — Quiet Day is the first implemented frame.** The Workshop v3 convergence (16 canonical frames, philosophy "The world knows how loudly to exist" (17:8873), audit 18:2) became the implementation design authority (`71154b0`), the Figma desktop-MCP bridge was proven end to end, and **Today — Quiet Day (17:481)** was implemented at `1a1e6ef` with the `personal-world-implement-figma` workflow: greeting-as-h1 with the known principal's name, health summary chip, the quiet companion message with the canonical rig and settle-gesture export, side-by-side activity panels that render only from real API data, and the accessibility floor intact. Gates: 600 backend / 361 frontend unit / 43 e2e / tokens / lint / framework validate / build. Two owner reservations recorded (companion presence scale; waves-ladder placement). Private UAT: 48 cases, 44 PASS / 0 FAIL / 2 REVIEW / 2 N/A.
- 2026-09-12 — **UAT round 1 passed; T15 cutover landed.** The legacy server-rendered UI is deleted: the React frontend is the only product UI, no `PW_FRONTEND` switch, honest 503 when dist is missing (no fallback UI). Settings truth fixes (server-refetch after writes, optimistic companion revert, dead theme-pack selector removed). Static files no longer use `immutable` cache — explicit ETag revalidation with 304 + error logging. Standing decision recorded: no persisted user data in the test environment until the owner calls it at least beta. Handoff: `.project/HANDOFF-UAT-ROUND-1.md`.
- 2026-09-12 — **P1 frontend foundation T1–T9 landed on `p1/frontend-foundation`** (T1–T4 merged via PR #20; T5–T9 at the convergence checkpoint):
  - T1/T2 (backend): sections registry + `GET/PUT /api/sections` per-person layout API, `GET /api/prefs/schema`; motion vocabulary `off | reduced (default) | subtle` with OS `prefers-reduced-motion` always overriding.
  - T3: `PW_FRONTEND` serving boundary (legacy default), SPA fallback with route precedence and traversal-safe allowlist, multi-stage Dockerfile (runtime image has no Node), CI image build; focus-ring token corrected per A11y §2.4.
  - T4: React prototype tracked as `frontend/` with the dependency diet (no Storybook/Chromatic/React Query/lucide/cva/Google Fonts); clean `npm ci` proven; lean Vitest/vitest-axe/Playwright/oxlint stack.
  - T5: `design/tokens.json` → `src/tokens.css` zero-dep generator, committed output, `tokens:check` CI drift gate, Tailwind `@theme` aliases only, self-hosted `@font-face` via `/fonts/*`, hex-literal and motion-lint gates.
  - T6: one typed API boundary (`lib/api.ts`): `pw_token` transitional auth, envelope unwrap, error mapping, 401→login / 503-setup routing, single `withStepUp()` write header.
  - T7/T8: accessible primitives — Dialog, Popover, LiveRegion (30s batched announcements), Drawer, Disclosure, StatusChip (luminance-only, closed vocabulary), CompanionSlot (sibling artwork/trigger), StepUpPrompt.
  - T9: AppShell (skip link, landmarks, rail/banner/bottom cascade, safe-area), SectionNav from `/api/sections` (hidden sections omitted, routes resolve), EmptyState/ErrorState, prefs applied to `<html data-pw-*>` before content.
  - Verification: Python 494 passed; `framework validate` healthy; frontend 147 tests green; build ~100 KB gz (budget 350 KB); tokens/hex/motion gates green; container CI-shape green.
- 2026-09-10 — completion plan adopted (`docs/history/PERSONAL-WORLD-COMPLETION-PLAN.md`) and **Phase 0 (stabilize) landed**:
  - P0.2 gitignore covers private runtime config (`config/*.local.json`, `config/principal.json`), frontend env/dist; ownership rule documented in `config/README.local.md`.
  - P0.3 `PUT /api/identity/principal` sets the caller's display name in private runtime state (`data/users.json`), step-up + persons only; a working-tree experiment that wrote plaintext provider keys into tracked config and served an unauthenticated React bundle was discarded, not merged. The client-side `VITE_*` bearer-token pattern is removed from the React prototype — no replacement client token exists by design.
  - P0.4 reminder scheduler no longer dies on first fire (`journal.append_raw` never existed); tick errors are visible state.
  - P0.5 `/login` returns its page; `POST /api/chat/test` requires auth; `POST /api/world/policy` → 409 on cemented keys (was 500); `GET /api/daily` is read-only, `POST /api/daily` runs the loop; reminder writes require the write-path gate.
  - P0.6 git test fixtures ignore host git config (suite green regardless of `init.defaultBranch`).
  - P0.7 public-safety gate scans every tracked text file for secret shapes with redacted reporting; tracked `config/*.json` must be zero-provider and free of inline secret keys.
  - P0.9 `scripts/safe-commit.sh` fixed (silently aborted in the clean bounded case), made executable, tested.
  - 425 tests passing; `framework validate` healthy.
- Personal World UI rescue: responsive shell and accessible navigation, progressive Today loading, working journal/service actions, a complete keyboard-friendly Chat loop, calm empty/error states, honest comfortable/high contrast preferences, and quieter personal-language/provenance presentation.
- Issue #8 phases 2-3: user provisioning API, multi-mode bootstrap keeps the instance token as primary, agent principals with owned narrow scopes, person-only guard on prefs/journal, revocation. 361 tests.
- Services launcher: /api/apps registry (step-up PUT, journal-audited) + dashboard "Services" card.
- Note composer: POST /api/journal + "Add a note" panel on Today.
- Login deep-links fresh installs to /setup-wizard (data-setup-needed).
- Nightly encrypted vault copy to NAS (VM cron 03:15, no-op until vault exists).

## 2026-09-09 — first-run wizard /setup-wizard shipped

### Added

- **A step-by-step first-run wizard for Personal World** for low
  cognition days: 5 short decisions, each skrippable; companions,
  token generation, optional vault passphrase, and a summary +
  Finish flow that start the dashboard. Uses the existing apliances
  contract; a11y contract kept (44px targets, dark, luminance only).

## Unreleased (2026-09-09 late)

### Added

- **Per-user preferences and journal isolation behind
  PW_IDENTITY_MODE.** Phase 1 of issue #8: /api/prefs and
  /api/journal pair route to the caller-person's own tree in
  multi mode; single mode returns the bootstrap-shared paths
  byte-identically. prefs PUT now requires step-up auth (same
  contract as journal write). Tests cover per-user isolation
  (alpha's scale never leaks to beta) and lazy-init absence
  as isolation proof.

Notable changes to Personal World. Entries are curated project
milestones, not a git-log dump. The project has no formal releases yet;
until a tagged release exists, the changelog tracks the evolving 0.1
development line on `main`.

## Unreleased

### Added

- **Figma-faithful dashboard theme (2026-09-07).** The dashboard now
  consumes the design truth the 0.1 pack shipped but never wired up:
  the 72px sidebar icon rail with 44px touch targets (top banner
  returns under 900px), self-hosted Young Serif display and Instrument
  Sans variable fonts (the `font.expressive`/`font.interface` design
  intent realized), the 72-glyph production icon sprite served at
  `/icons/sprite.svg`, the greeting block + motif-badge + section
  rhythm from `today-rylee-theme`, and the rylee accent corrected to
  the design's rose `#b57f8b` (replacing an invented pastel). New
  public routes serve only decorative static assets (icon sprite,
  OFL-licensed font binaries). Palette tokens in `design/tokens.json`
  are untouched; the accessibility floor is unchanged and all 25
  dashboard tests pass. Design source: Figma file VATVojyJZT9HKx0CrDS0yr
  frame 3:2147, extracted via the Figma MCP bridge 2026-09-07.
- **Accessibility contract discoverability + current-state entry point
  (2026-09-07).** The four canonical accessibility documents
  (`ACCESSIBILITY_CONTRACT.md`, `SCREEN_READER_WALKTHROUGH.md`,
  `RESPONSIVE_RULES.md`, `PREFERENCES_SCHEMA.json`) moved from
  `design/handoff/` (an Archived directory) to `docs/accessibility/`
  so the non-negotiable contract no longer sits inside a do-not-edit
  area. `AGENTS.md` now routes UI work to the contract directly. A new
  root-level `STATUS.md` is the current-state entry point: it answers
  "where do I look to know what is happening right now?" by deferring
  to the homelab repo's `docs/agent/CHECKOFF.md` instead of
  duplicating epoch state. Four new tests in `tests/test_docs.py`
  guard the canonical location, the AGENTS.md pointer, the STATUS.md
  pointer (and its no-duplicated-status rule), and block the archived
  copies from coming back. Repo truth stays single-sourced; the
  archived `design/handoff/` directory is now purely historical.
- **Chat surface with local-AI integration (2026-09-07).** Chat is a
  first-class dashboard destination backed by `POST /api/chat` and a
  provider-neutral `ChatContract`. Two adapters ship: `ollama`
  (Ollama's native API) and `openai_compat` (any OpenAI-compatible
  endpoint). The model observes a trimmed read-only world snapshot —
  capability statuses, actors, intents, policies, world-classified
  lore, recent journal events, source-repository summaries — and
  degrades honestly: `not_configured` with no provider, an inline
  error card when a model is unreachable. The core boots and stays
  fully usable with zero AI.
- **Dashboard rebuild on the canonical token system (2026-09-07).**
  Five-section navigation (Today, Chat, World, Journal, Settings),
  aubergine palette from `design/tokens.json`, status chips that lead
  with text words, journal kind-filtering, source-repository and
  update read views on World, and honest empty states throughout.
- **Companion runtime (2026-09-07).** The five approved companion
  source rigs ship byte-identical in the package and render at the
  brand lockup and Chat surface; companion selection and the Rylee
  accent palette are live preferences applied server-side and
  client-side.
- **Live preference editing (2026-09-07).** Text scale, density, touch
  targets, companion, and accent change the UI immediately and persist
  to the world state via `PUT /api/prefs`; the accessibility floor
  remains non-lowerable.
- `POST /api/chat`, the `reasoning` capability registry seam, and a
  19-test chat suite covering context trimming, private-lore
  exclusion, provider substitution, and fail-honest API behavior.

### Added (2026-09-08/09 — container bring-up session)

- **MiMo cloud-chat provider wired.** `openai_compat` connection to
  the Xiaomi MiMo endpoint ships as a private runtime config
  (`config/connections.local.json`, gitignored; template +
  `config/README.local.md` document the shape). Compose forwards the
  provider key by env indirection; no credential enters the repo.
- **Vault is real.** The vault endpoints were stubs returning
  hardcoded empties; now one persistent `Vault` instance backs
  unlock/lock/set/delete/names, secrets persist encrypted to
  `/data/vault.enc`, and setup-with-passphrase writes the encrypted
  file immediately. The Dockerfile installs the `cryptography` extra
  (was silently falling back to base64) and the lockfile carries the
  crypto deps (later bumped by dependabot to 50.0.0 with all gates
  green).

### Fixed (2026-09-08/09)

- Container didn't ship `git`, so the native source-control baseline
  reported `git binary not found` and the dashboard had no repository
  status. The image now installs git and the compose config points
  the native baseline at a container-internal clone
  (`/data/repos/personal-world`); source-control status/repro health
  verified live in-container.
- `compose.yaml` did not forward chat-provider API keys, so chat
  tested `401 Unauthorized` even with correct credentials. Keys now
  flow via env indirection (`XIAOMI_MIMO_API_KEY`), matching the
  provider contract's secret rule; chat verified working end-to-end
  (`mimo-v2.5-pro` replies through the container).
- Vault endpoints were stubs (see Added above).

### Changed (2026-09-08/09)

- Deployment image now installs `--extra test --extra crypto`;
  `uv.lock` refreshed to include `cryptography` (43.0.3 -> 50.0.0
  via dependabot PR #13).
- World seeded for daily use: 26 facts, 4 open intents, 4 policies
  (chat is read-only; private lore never exported; secrets never in
  chat context), 2 reminders (morning check-in, evening close-out).
- Repo state: GitHub + Gitea synced at `12f8e33`; CI green on every
  push of the session.

### Fixed

- Dashboard `load()` used `Promise.all()` on a plain object (not
  iterable), so every load threw and reported the core unreachable
  even when all APIs returned 200 (2026-09-07).

### Changed

- History sanitization: removed operator deployment endpoints and
  personal identifiers from the tracked default configuration and from
  the repository's public history (2026-09-07).
- The tracked `config/connections.json` now ships as a zero-provider
  baseline; an example file documents the wiring shape using reserved
  documentation hosts.
- New `tests/test_public_safety.py` regression gate blocks private
  endpoints (RFC1918 ranges and known operator hostnames) from
  re-entering shipped defaults.
- CI workflow actions bumped to current major versions
  (`actions/setup-python` v7).

## 2026-09-06 — the 0.1 bootstrap line

The repository went from empty skeleton to working application,
design system, and CI in a single day. Major milestones, in order:

### Added

- **Core world model** — facts, intent, policy, lore, capabilities,
  providers, journal, packs, and export contracts with
  world/private/secret classification (`feat(core)`).
- **Standalone deployment** — compose file, healthcheck, and CI
  workflow (`feat(deploy)`).
- **Live provider wiring** — Gitea and LangGraph adapters, gatus
  health fallback (`feat(lab-profile)`), later joined by a real
  LangGraph memory search provider with an epistemic taxonomy
  (`feat(memory)`).
- **Candy observation loop and dashboard foundation** — status
  vocabulary, stale semantics, attention items
  (`feat(v0.1)`).
- **Safe update flow** — check/preview/apply/verify/rollback
  (`feat(updates)`).
- **Presentation preference plumbing** with an enforced accessibility
  floor (`feat(prefs)`).
- **Native git-ish source control workflow** — zero-provider baseline
  for the source_control capability (`feat(source-control)`).
- **Framework tooling** — `personal-world framework validate`,
  design-tool independence tests, export portability gates
  (`feat(framework)`).
- **Apache-2.0 license** and integration leakage tests.
- **Design handoff for the Figma stage** — the sanitized product spec,
  operations guide, and the archived 0.1 spec package with Figma
  exports; canonical tokens reconciled to the aubergine palette.
- **Theme Pack Framework and personal theme pack specs** — swappable
  companion/palette packs that cannot modify the accessibility
  contract.
- **Companion character system** — five companion source rigs
  (Personal World, Mermaid, Little Helper Robot, World-tree Squirrel,
  Tacos & the Morning Paper), Lottie production lessons, the
  production icon system (72 deterministic SVGs), and the full
  Companion System & Chat architecture doc.
- **Screen SVG library** — Today/Journal/Settings/Chat screens across
  generic and personal themes, narrow and desktop layouts, with
  companion integration and chat navigation.
- **Public hardening pass** — visitor onboarding (README start-here
  table, CONTRIBUTING, SECURITY), issue/PR templates, Dependabot
  configuration, secret-pattern sanitization in test fixtures, pinned
  CI dependencies.

## Before 2026-09-06

The repository did not exist. There are no earlier releases, tags, or
hidden history: the first commit is `chore: bootstrap personal-world
repository skeleton` (2026-09-06).
