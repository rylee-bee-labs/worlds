# Construction-era and epoch narrative (historical)

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/CURRENT.md`) · **Read this if:** you want the dated 2026-09-12→14 feature-slice narrative. · **Superseded by:** `.project/CURRENT.md`.

**In short:** the construction-era narrative (Projects workspace, journal supersede, agent-sync estate, Gitea retirement, GHCR, the identity pass and the integration truth pass), extracted verbatim from `.project/CURRENT.md` on 2026-09-15 so the current-state pointer stays a summary. Counts and feature claims are as of the dates shown and have not been re-verified; for current state read [`.project/CURRENT.md`](../../.project/CURRENT.md), and for implemented scope read [`README.md`](../../README.md) and [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md).

## What works today

See `README.md` "What makes it different" / architecture docs for the
durable description. As of this trunk: legacy server-rendered dashboard
+ full React frontend (Today, Interests, Media, Projects, Lab, Chat,
Journal, Vault, World, Settings, Login, Setup) with real headings and
no card-chrome composition drift on Today/Journal/Vault; the two
previously-shipping accessibility bugs below are fixed everywhere, not
just on the branch that found them.

**Projects workspace v1 (2026-09-12, `85067a7` + `f72f47c`):** the Projects
section now renders the REAL repository table from the native
source-control baseline (`GET /api/source-control/status`): one row
per discovered repo with branch, dirty/ahead/behind, last commit; a
quiet glance line (counts only; clean stays quiet); per-repo
provenance (path/revision/remote) and recent-commit drill-in
(`GET /api/source-control/history`). Selecting a repo is a shareable
`?repo=` deep link, and the World Assistant context carries it as the
observed selected entity ("looking at personal-world"). No search
paths configured → the same honest EmptyState + knob as before. The
e2e fixture points the baseline at the repo itself, so CI exercises
real git — no fabricated rows anywhere. Frontend type now mirrors the
backend `repository_status()` exactly (9 previously-dropped fields
recovered).

**Journal audit trail (2026-09-12, `b756f49`):** the Journal screen
gained a lazy Level-4 "Audit trail" disclosure — the backend
AuditRenderer's full technical log (provenance on every line), shown
verbatim on request; zero fetches in the calm default view. Finishes
the "understand exactly what happened" + nerd-mode transparency rows
for journal.

**Journal correction/supersede workflow (2026-09-12, `f86b1cc`,
second propose→approve→act workflow):** any journal entry can be
corrected without erasing it. "Correct this entry" opens an inline
approval panel (original vs proposed, effect/risk/recovery, "Nothing
has changed yet"); explicit approval appends a corrected entry that
links back via `supersedes` — the original row is NEVER rewritten
(append-only NDJSON; currency is derived from links). The calm view
shows only current versions; each corrected entry carries a "Corrected"
note and a "View history" disclosure exposing the full chain with
reasons and timestamps. Idempotent retries (same target + same text →
already-applied, no duplicate); conflicting second corrections are
rejected honestly; failures leave the original current. Every
correction journals an APPROVAL audit event answering what/old/new/
proposer/approver/reason/mechanism/when. Repeated corrections are
linear (A→B→C; branching rejected). Backend tests (11) + frontend
tests (6) + live 10-point browser walkthrough incl. keyboard, focus
ring, 200% reflow, reduced motion.

**Assistant-drafted journal correction proposals (2026-09-12,
`04c9c76` — assistant participation, suggestion is not authorization):**
Personal World can now PREPARE a Journal correction without any
authority to apply one. The chat system prompt teaches ONE tiny
fenced `PW-PROPOSAL journal_correction` block (entry_ts,
proposed_text, reason, evidence_summary) that the model MAY emit
when later entries contradict an earlier one. `chat.py
extract_proposal` validates it STRICTLY (exact header, all four
fields, caps 2000/200/300, no unknown/duplicate/empty fields);
anything malformed degrades to ordinary visible text, never a chat
failure. `api.py` re-validates the target against the REAL journal
(nonexistent or already-superseded targets yield no proposal) and
serves it as typed `proposal` metadata alongside the human-readable
reply. The ChatPanel suggestion card renders the draft labeled
"A possible correction, drafted by Personal World" with
proposed text/reason/evidence, the boundary sentence "Preparing is
not approving — nothing changes until you approve it in the
Journal", and two choices: **Prepare correction** (stash + navigate
to `/journal?correct=<ts>` — pure navigation, ZERO mutation calls)
or **Not now** (dismiss). JournalScreen pairs the stashed draft
with the URL target (timestamps compared as instants — `Z` vs
`+00:00` both valid), opens the EXISTING correction panel
automatically for that entry, prefilled + labeled "Personal World
drafted this proposal … review it, edit it freely, or close it",
focus lands in the editable text. The person edits freely; the
normal "Nothing has changed yet" boundary and explicit approval
apply unchanged; on approval the supersede body carries
`drafted_by: "Personal World (assistant draft)"` (allow-listed
server-side; unknown values fall back to the default) and the
APPROVAL audit event records the true story: "proposed by Personal
World (assistant draft), approved by the owner via the Journal
screen, reason: …". The assistant has NO access to the supersede
endpoint; ordinary chat "yes" cannot mutate anything (tested);
the step-up is unchanged. Live-verified end to end with the real
local Qwen model producing a real server-validated proposal for a
seeded out-of-date entry (porch light), full
suggest → prepare → inspect → edit → keyboard-approve → corrected
current → history chain → reload persistence → audit walkthrough;
a11y: card understandable without color, keyboard activation,
focus lands in the textarea, 2px focus-visible ring on all
actions, 200% reflow clean, reduced motion fine, no modal.

**GitHub count honesty fix (same commit):** open-PR and open-issue
counts are now EXACT via GitHub search `total_count` (the old
per_page=100 list length silently capped at 100 — octocat/
Hello-World's 1203 open PRs proved it). Search failure yields
honest unknown (null) counts, never zeros; issue count is searched
directly instead of derived from open_issues_count. Chat context
journal lines now show the exact ts key (both ISO spellings) so
proposals can reference real entries.

**Play-Nice product identity (2026-09-12, README + this pass):**
"Project Worlds is a Play-Nice product" — README carries the
owner-authored "A Play-Nice product" section (Play-Nice governs
cooperation: Rylee, Personal World, agents, providers; Project
Worlds stays authoritative for its architecture, data, UI, domain
behavior) with the canonical link
https://github.com/Rylee-Bee/play-nice-contracts and the
adoption/current/decisions anchors. Wording adopts the contracts
without any certification or endorsement claim — the repository
is the evidence. `.project/DECISIONS.md` now exists as the durable
decisions record the README references (append-only; dated
entries). Rebase note: the owner's parallel chore(readme) commit
was honored (their wording kept; my overlapping section dropped)
and its broken `.project/DECISIONS.md` link fixed by creating the
file.

**agent-sync as the project-status sensor (2026-09-12, slice
`9d41bd6`–`42a6f8b` — observation is not mutation):** Project Worlds
now consumes the SAME project truth Rylee sees from
`agent-sync status --all --format json` — no second Git-state
implementation exists inside Project Worlds. Architecture:
Git/.project/.agent → agent-sync (computes project state) →
Project Worlds (presents) → Personal World (explains) → Rylee
(decides). The sensor is `providers/agent_sync.py`
(`AgentSyncProjectSensor`): one subprocess invocation per call,
argv-only, 60s bounded timeout, parses agent-sync's documented
`play-nice/repo-status-v1` JSON and normalizes honestly (closed
vocabularies enforced; unknown preserved as `null`/`unknown`, never
filled; records without the schema marker skipped, never guessed;
per-repo `error` records kept with their error text; **exit code 1
is a valid work-to-do observation, not provider failure**). Failure
model verified: command absent / timeout / malformed JSON / non-list
→ honest `unavailable`, never a crash, never partial records; sensor
absence never breaks anything else. Endpoint `GET /api/projects/status`
(read-only, auth-gated, envelope-kept). Projects screen gained the
estate panel: five DISTINCT categories (quiet / local work /
unpublished / diverged / unknown) never collapsed into one warning;
calm glance shows only categories that exist and stays "settled-quiet"
when nothing needs saying; published-with-local-work presented
calmly (NOT broken); per-project human sentences with no Git
commands suggested; technical guts (SHAs, tree counts,
safe-to-leave, Play-Nice, work state, observed time) behind ONE
disclosure. Today gained a bounded "Projects" section: attention
projects get a sentence + "See Projects" link (max 3, remainder
counted), local work one calm mention, unknown honest, settled
estate one quiet line, sensor absent → section invisible (Today
stays calm). Category vocabulary shared via
`frontend/src/lib/project-status.ts` (no duplicate categorization).
Personal World's chat context gained `## Projects (agent-sync
observation)`: a compact bounded projection (one line per non-quiet
project, quiet projects as ONE count line, SHAs NEVER in context,
unknown preserved); sensor absent or failed → NO block (estate
unknown, not empty). Live-verified with the real local Qwen: it
answers "which projects need attention", "what is unpublished",
"where is local work", "is VEFR safely published" truthfully from
the real estate (diverged/unknown states preserved, no fabrication).
agent-sync itself was ported to THIS machine (Bazzite) at its
canonical `~/.agents/` root from the WSL bundle —
`agent-sync --statustest` OK offline; its Bazzite
`settings.yaml -> projects:` registry lists the six verified local
repos (personal-world, vefr, rylee_lore, munr, play-nice-contracts,
projects/homelab); homelab-dns deliberately EXCLUDED (its git remote
URL embeds a credential and must not surface in any Project Worlds
view), non-repos and third-party clones excluded. Live display
matches `agent-sync status --all` exactly (6 projects; honest
unknowns for the three remotes unreachable from this machine).
Backend 622, frontend 337, e2e 43 green; live browser a11y probes:
720px no horizontal scroll, keyboard focus ring solid 2px, 44px+
targets, reduced motion fine, non-color state distinction (words +
sr-only chips), technical guts only behind disclosure. One small
test-race fix in e2e PROXY-b (one-shot `isVisible()` read raced the
wrapped-banner relayout after `setViewportSize` on slower hosts;
replaced with retrying `toBeVisible()` — same assertion, no race).
**No mutation capability added anywhere** — status observes,
presentation presents, the assistant explains; nothing in this
slice can touch a repository.

**Project-state trust pass (2026-09-12, rylee_lore remote truth +
observation age):** Two sections. (1) The rylee_lore "diverged"
finding was investigated deterministically and classified **A:
STALE REMOTE CONFIG** — the configured remote still pointed at
the pre-rename `rylee-bee-labs/rylee_lore` URL (GitHub account renamed
to Rylee-Bee 2026-09-12; `gh api` shows rylee-bee-labs/rylee_lore
redirects to Rylee-Bee/rylee_lore, `fork: false`, and the
`rylee-bee-labs` user 404s), and the true local↔remote relationship was
strictly BEHIND (local `ea089df` = merge-base, 0 local-only
commits, 21 remote-only commits) — agent-sync's "diverged" was
its honest fallback (it compares against `ls-remote` SHAs without
fetching; rev-list against an unknown SHA fails → "diverged").
The remote URL was corrected to
`https://github.com/Rylee-Bee/rylee_lore.git` (config line only;
NO reset/rebase/merge/pull — the checkout is still behind 21
commits, an owner decision; tree clean before/after, nothing
absorbed). The estate now truthfully reports rylee_lore `behind`.
The pre-existing play-nice-contracts `diverged` (remote moved to
`2036692` past the pinned `0cee065`) is REAL divergence —
preserved and reported, an owner decision. (2) Observation AGE
surfacing: every project-status surface now distinguishes WHAT
was observed from WHEN it was observed. agent-sync's own
`observed_at` stays the only freshness source (no second clock);
freshness is DERIVED (`fresh|stale|unknown` + `age_seconds` in the
API) and is a SEPARATE dimension from state — stale + diverged is
still diverged, observed some time ago; staleness never converts
state to unknown. Threshold = the product-wide lab_state 30-minute
`FRESHNESS` convention (`STALE_AFTER` in the sensor mirrors
`lab_state.FRESHNESS`, asserted by test; no settings system).
Shared computation: backend `providers/agent_sync.freshness()` +
ONE frontend helper `lib/observation-age.ts` (relative ages,
pluralization, injectable now for deterministic tests) — no
per-screen date math. Surfaces: Projects age line on the estate
panel ("Observed 4 minutes ago by agent-sync — a dated
observation, not live truth."; stale suffix " · may be stale",
never ERROR/OUTDATED/DANGER vocabulary) and in the per-project
guts ("Observed just now (2026-09-12T15:15:17Z)"); Today adds ONE
quiet line only when stale ("Project status may be out of date —
last observed 47 minutes ago." when quiet / "Project status was
last observed 47 minutes ago." when attention exists; fresh → no
extra ink); Personal World's context block carries calm age prose
("Project observations: 47 minutes old; may be stale." / "just
now") so the assistant hedges honestly — live-verified: it
answers "how fresh is that information?" from the age line and
never presents old observations as current. Missing/invalid
observed_at → no age line anywhere (an unknowable age is not a
stale age) and "Observed at an unknown time" on Projects (a
fabricated "just now" from the prior slice was removed — a truth
bug this pass fixed). No new polling, no cache, no refresh
mechanism. Backend 634 (12 freshness tests), frontend 354 (13
helper-unit + 4 screen age tests), e2e 43; live: 720px zero
overflow, keyboard-reachable guts with 2px focus ring, no
color-only meaning, reduced-motion fine.

**Gitea retirement + GitHub enrichment + public README/screenshot
pass (2026-09-12, slice complete):** Gitea is retired from the live
architecture. `GiteaEnrichment` and `/api/source-control/rollups` are
removed (the endpoint 404s); the generic forge adapter in `adapters.py`
remains as substitution-proof registry machinery, no longer a
supported live provider; `GITEA_TOKEN` is gone from compose and
examples; GitHub is the supported remote enrichment provider.
Model: LOCAL GIT TRUTH (canonical: existence, branch, dirty,
ahead/behind, local history) + OPTIONAL GitHub enrichment
(`providers/github.py` — read-only `gh api` argv calls over the host's
existing authenticated gh session; NO credential management in the
app; structured `unavailable`/`not_github`/`not_configured` states;
`not_github` answered from the local remote URL without needing gh).
Surface: `GET /api/source-control/enrichment?repo=<name>` + the
Projects drill-in "GitHub activity" disclosure (open PRs, open
issues, remote default branch, last remote push, canonical slug/url
with per-field provenance). Quiet degradation verified live WITH and
WITHOUT gh: absent → one sentence, native table untouched.
README rewritten for public landing (screenshots at top, honest
what-works-today, quick start with real clone URL Rylee-Bee/personal-world,
deeper-docs table); five sanitized screenshots under
`docs/screenshots/` captured from the real running app on a fixture
demo world (`demo-world` repo + seeded garden/fig-tree journal entries
with one corrected entry showing the history chain). Safety audited:
no tokens, no hostnames/IPs, no private repos (octocat/Hello-World is
intentionally public), no browser chrome leaks, demo commits re-
authored to "Demo Person". Historical Gitea references preserved in
CHANGELOG/ADR/DESIGN-HANDOFF/completion-plan; current-architecture
docs (ARCHITECTURE, NATIVE-BASELINE, PROVIDERS, ROADMAP, AGENT_POLICY
context) updated; NATIVE-BASELINE anti-pattern illustrations kept
(conceptual, still truthful).

**First propose→approve→act workflow (2026-09-12, `f0f64e6`):**
from a selected repository on Projects, the screen proposes a
read-only status re-check and explains WHAT/WHY/TOOL/RISK/EXPECTED;
nothing runs before the explicit "Approve and refresh" button. The
act is `POST /api/source-control/refresh` (step-up gated) which
re-runs the native git status for that repo and journals a
PROVIDER_ACTION audit event answering who proposed, what was
approved, which tool ran, what came back, and when. The panel shows
explicit has/has-not-happened state through proposed→running→done/
failed; repeated use re-proposes rather than auto-running. This is
the FIRST approval workflow only — the pattern (not an engine) for
later, higher-risk actions.

**Context-aware World Assistant (2026-09-12, implementation run
`ce23f3f`):** the Drawer-hosted assistant now knows which section it
was opened from. The shell derives route/section (GET /api/sections
registry supplies the label) and POST /api/chat accepts an optional
`context` envelope rendered into the system prompt as observed UI
location — provenance, never authority: unknown sections degrade to
honest "unknown", malformed context never breaks conversation, and
the standalone /chat route stays the global surface. The panel shows
"You opened this from <section>" and swaps in section-local
conversation starters. Backend 517 tests, frontend 293, e2e 42/42
incl. axe; live-browser verified on /journal, /vault, /chat.

**Two accessibility bugs fixed and verified on this exact trunk**
(both were live/shipping on old `main` before this unification — not
hypothetical):
- Invisible keyboard focus ring: `design/tokens.json`'s `focus.ring` was
  an unresolved token reference plus invalid `outline` shorthand syntax;
  browsers silently dropped the whole declaration. Fixed to a literal
  resolved value; `tests/test_design_tokens.py` now checks real CSS
  validity, not a placeholder string.
- OS `prefers-reduced-motion` silently overridden by a saved "subtle"
  motion preference in the React port (JS inline styles beat the
  non-`!important` CSS media-query rule). Fixed in
  `frontend/src/lib/prefs-context.tsx` to check `matchMedia` and force
  the reduced tier unconditionally, with a live-change listener.


## Identity pass (2026-09-12): what changed vs what intentionally didn't

Audited references to "Personal World" / "personal-world" /
"PERSONAL-WORLD" across the repo (~85 files matched a grep). Did **not**
blindly rename all of them. Classification used:

- **Updated (human-facing product identity):** `README.md` (title,
  tagline, "Why it exists"), `.project/project.yaml` (`name` +
  `purpose.summary`), `.project/README.md`, this file.
- **Left unchanged — technical/repository identifiers** (renaming is a
  separate, deliberately deferred migration per explicit instruction):
  `pyproject.toml` (`name = "personal-world"`), the `personal_world`
  Python package, the `personal-world` CLI command, `frontend/package.json`
  (`personal-world-frontend`), `compose.yaml`, `config/`, CI workflow
  files, the GitHub repo slug itself.
- **Left unchanged — character identity, not product identity:**
  "Personal World" is also the proper name of one of the five companion
  residents (the default/generic mascot — see
  `design/COMPANION_INTEGRATION.md`, `design/assets/companions/personal-world/`).
  This is a deliberate, separate naming choice (the default companion
  shares its name with the product by design) and was NOT renamed —
  conflating a character's name with the product name would be a content
  bug, not an identity update. Flagged here as a genuine open question
  the product owner may want to resolve later (does the default
  companion get renamed too, or does it keep its established identity
  regardless of product branding?) — **not decided in this pass.**
- **Left unchanged — historical documents:** `CHANGELOG.md` entries,
  `design/handoff/*` (archived Figma spec package), `docs/p1/FOUNDATION-SPEC.md`,
  ADRs, dated handoffs. These remain truthful to the period they
  describe; rewriting them would falsify history for no benefit.
- **Identity cleanup complete (2026-09-12, second pass):** the
  deferred policy-doc prose above was updated in a bounded follow-up
  pass (`docs/ACCESSIBILITY_CONTRACT.md` → under
  `docs/accessibility/`, `ARCHITECTURE.md`,
  `HUMAN_RELIABILITY_CONTRACT.md`, `PERSONAL-WORLD-FINISH-LINE.md`,
  `PERSONAL-WORLD-COMPLETION-PLAN.md`, `INDEX.md`, `NATIVE-BASELINE-
  AND-ENRICHMENT.md`, `OPERATIONS.md`, `PROVIDERS.md`, `DESIGN-HANDOFF.md`,
  `ROADMAP.md`, `SECURITY.md`, `README.md`, `AGENT_POLICY.md`,
  `AGENT_CONTRACTS.md`, `CONTRIBUTING.md`, `frontend/README.md`, current
  `design/` docs, issue templates, `compose.yaml` header comment). Each
  occurrence was classified first; rule/technical content is unchanged.
- **Runtime brand pass COMPLETE (2026-09-12, `f0f64e6`):** every
  PRODUCT-BRAND runtime string now says "Project Worlds" — the shell
  brand lockup, login h1, setup headings + default world name ("My
  Project Worlds"), SPA/index titles, legacy dashboard titles and
  error copy, chat provenance/footnote, FastAPI title, theme-pack
  author. COMPANION references intentionally keep "Personal World"
  (companion selection lists, "A conversation with Personal World"
  humanizers, companion-context names). TECHNICAL IDENTIFIERS and
  HISTORICAL TEXT unchanged, as before.
- **Historical Personal World references intentionally retained:**
  `CHANGELOG.md`, `docs/adr/`, `docs/p1/FOUNDATION-SPEC.md`,
  `design/handoff/` (archived Figma package), `docs/FIGMA-HANDOFF-LESSONS.md`,
  dated postmortems (`design/SVG_POLISH_NOTES.md`), the
  `PERSONAL-WORLD-*` **filenames** and their cross-links (stable
  identifiers, not prose), the screen-reader walkthrough's observed
  `Personal World — <page>` runtime title pattern (it describes the
  built interface), and every technical identifier. These are legitimate
  history or deliberate stability, not stale prose.
- **Technical identifiers intentionally remain `personal-world`:** repo
  slug, Python package, CLI command, npm package, compose service
  names, schema URIs (`personal-world/…`), CI images, config paths.
  Renaming any of these is a separate future migration decision.
- **New product work may begin** — trunk unified, identity cleanup
  complete; the only open identity question is the companion name below
  (which does not block product work).

## In-flight / untracked

`frontend-v2/` and `.bcode/` are pre-existing local experiments,
unrelated to any pass, still untouched. **Tree-state honesty note
(2026-09-12): the working tree is "clean of tracked changes", NOT
"clean" in the absolute sense — `.bcode/`, `frontend-v2/`, and a
root-level `node_modules/` sit UNTRACKED (not gitignored; only their
inner `node_modules/`/`dist/` subtrees are). They are intentionally
neither absorbed into commits nor deleted; every commit stages
explicit paths only.**


## Integration truth pass (2026-09-13/14)

A connective-tissue pass verified and repaired agreement between
components. Hypotheses from the handoff were tested against current
code before changing.

### Confirmed and fixed

- **Authorization boundary (P1):** `ToolRegistry.invoke()` now
  structurally blocks execution tools — the model can propose but
  cannot approve or execute. Proposal tools (requires_approval=True)
  are callable by the brain; they create pending proposals without
  mutating the target domain. Approval requires server-side owner
  action through the step-up-gated API path. Tests in
  `tests/test_authorization_boundary.py` (19 tests) prove the full
  propose→approve→execute boundary.
- **Step-up authorization (P2):** Three Connections routes called
  `require_step_up(request)` without `await`, creating an unawaited
  coroutine that never enforced the check. Fixed to use
  `Depends(require_step_up)`. Session-based step-up is now checked
  in `_step_up_authorized` alongside loopback/private/header paths.
  **Honest description:** this is trust elevation, not fresh
  re-authentication or MFA. Three paths grant write access: (1)
  session elevation flag (300s window), (2) trusted local/private
  network, (3) X-PW-StepUp header from a trusted proxy. Genuine
  fresh re-authentication is NOT implemented — a known gap.
- **Configuration truth (P3):** `ConnectionManager` is now the
  canonical config resolver. A `resolve_native_config()` function
  transforms flat UI config (schema-driven, `_adapter` discriminator)
  into the nested shapes native providers expect (`sources[]`,
  `targets[]`, `type` discriminator). One save path (UI →
  connections.local.json) feeds all consumers (provider constructors,
  API endpoints, brain tools). `build_adapter()` treats unresolved
  secret references as unresolved — they are never passed upstream
  as credentials.
- **Connections UI round-trip (P4):** Form inputs lacked `name`
  attributes, so `FormData` sent blank values for Test connection.
  Existing connection data was fetched but never populated
  `initialValues`. Both fixed. Native config (calendar, notifications,
  etc.) now fetches initial values from `/api/connections/config`.
- **Execution semantics (P5):** Reminder proposals now execute
  through the real scheduler: approved→executing→executed on success,
  approved→executing→failed on failure. World intent/fact mutations
  persist via `save_world()` in the API execution path. Reconciler
  remains "prepared" (no mutation actually occurs).
- **Vault fail-closed (P6):** Vault now requires real `cryptography`
  package — no base64 fallback. Status reports actual encryption
  capability, not a hardcoded `true`. Without crypto, vault is
  unavailable (fail-closed). Tests in
  `tests/test_vault_fail_closed.py` (14 tests) prove: crypto present →
  encrypted, crypto absent → refused, status truthful, no secret
  values in audit.

### Test counts (verified)

- Backend: 770 collected / 770 passed / 0 failed (with crypto)
- Backend: 754 collected / 751 passed / 0 failed / 3 skipped (without crypto)
- Baseline (main 0dca309): 717 collected / 717 passed / 0 failed
- Delta: +53 tests (19 authorization + 14 vault + 14 secret ref
  + 6 reminder execution)
- Frontend: 76 failed / 258 passed / 334 total (pre-existing on main)
- Framework validate: 0 violations

### Remaining gaps (honest)

- **Proposal persistence:** Proposals are in-memory (process state).
  A restart loses pending proposals. Acceptable for current
  single-process architecture; needs persistence if multi-process.
- **Vault secret_ref resolution:** Provider schemas define
  `secret_ref` fields but no vault-to-provider resolution exists.
  Unresolved references cause adapters to return None (not_configured).
  Env var indirection works as the credential path.
- **Reconciler apply:** Returns "prepared" — actual provider apply
  requires adapter integration not yet built.
- **Fresh re-authentication:** Step-up is trust elevation (time
  window + network + header), NOT fresh password/MFA verification.
  Genuine re-authentication is a remaining gap.
- **Frontend test failures:** 76 pre-existing failures on main at
  0dca309. Not caused by this pass.
