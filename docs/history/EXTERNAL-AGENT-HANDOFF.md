# EXTERNAL-AGENT HANDOFF — parallel lanes for Worlds

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/CURRENT.md`) · **Read this if:** you need the 2026-09-16 parallel-lane working plan and its file-ownership rules. · **Superseded by:** `.project/CURRENT.md`.

**In short:** a dated 2026-09-16 handoff that split work into four disjoint lanes (`station` accessibility, chat streaming, live-IdP harness, restore drill). Kept for provenance; its states and lane assignments are not current. Since the 2026-09-22 flip the interface is `ui/` and the server-rendered Station is retired (kept as a theme package); `frontend/` paths here are the deleted pre-flip tree.

Read fully before copying anything from it. It was written for base `main` @ `c16a07c`.

## The soul (non-negotiable)
DNA: smallest-reliable-first · depth-on-demand · soft-by-default · everyone-at-any-level-included.
Accessibility floor is law (`docs/accessibility/ACCESSIBILITY_CONTRACT.md`): 44px targets,
AA contrast, keyboard, reduced-motion, no colour-alone status, honest states.
Writes ALWAYS gated (observe→propose→approve→act). No fake data, ever.
Play-Nice contracts bind you (`.project/contracts/adoption.yaml`).
Full picture: `docs/PROJECT-WORLDS-MASTER-HANDOFF.md` · `docs/ROADMAP-AND-TODO.md`.

## Current verified state (don't re-derive)
Backend live: auth/session/step-up, world/journal(+FTS)/reminders/prefs, proposals
write-safety, vault fail-closed, git reads, multi-user per-principal namespacing,
single chat loop + lenient small-model tool-calling + templates + `/api/templates`,
generic OIDC (Authelia-ready, stub-verified), first-run setup wizard, `/api/manifest`
(the Lego box, 110 curated endpoints verified against live routes), `/station/`
same-origin Station with real-data wiring for needs-you/journal/prefs.
Tests: full suite green except 4 pre-existing `test_updates.py` docker-daemon failures.
`framework validate` = 0 violations.

## IN FLIGHT — DO NOT TOUCH these files
- Encrypted backup lane: `src/personal_world/worlds_backup.py`, `tests/test_worlds_backup.py`,
  `docs/WORLDS-BACKUP.md`, `station/backup-ui.js`, and the `worlds backup/restore`
  subcommands in `src/personal_world/cli.py`.
- CLI-parity lane: `src/personal_world/cli_dispatch.py`, `tests/test_cli_dispatch.py`,
  `docs/CLI-REFERENCE.md`, and its one additive `cli.py` registration.
If you need `cli.py`, add NOTHING; note it in your receipt instead.

## AVAILABLE LANES (pick ONE; own ONLY its files)
> **LANE STATUS 2026-09-16:** LANE A and LANE C are TAKEN by the orchestrator's
> own agents. External agents should take **LANE B** or **LANE D** (or propose a
> new disjoint lane in your receipt first).
### LANE A — Station accessibility e2e gates
Own: `frontend/e2e/station-*.spec.ts` (or `tests/e2e_station/`), nothing else.
Do: Playwright+axe against `/station/` (login first): colour-contrast enabled,
44px audit, keyboard journey (map→drill→dive→back), reduced-motion, 200% reflow,
focus-visible, no console errors. Acceptance: all green on a seeded world;
honest-skip with reason if browser unavailable.

### LANE B — chat streaming + history persistence
Own: streaming in `src/personal_world/chat.py`, the `/api/chat` route region of
`src/personal_world/api.py`, `tests/test_chat_stream.py`. Do NOT touch other api.py regions.
Do: SSE/streaming responses + per-principal persisted history (reuse
`chat_history.py`); honest `unavailable` when no brain configured; keep write-safety.
Acceptance: stub-provider stream test + history round-trip + no-brain honesty test.

### LANE C — live-IdP (Authelia) integration harness
Own: `tests/test_oidc_live.py`, `compose.authelia-test.yaml`, `docs/oidc-live-test.md`.
Do: containerized Authelia test env; real discovery→login→callback round-trip when
`PW_TEST_AUTHELIA=1` + creds env present; otherwise skip honestly with reason.
Never embed secrets; read from env only.

### LANE D — restore drill (starts AFTER backup lane lands)
Own: `scripts/restore-drill.sh`, `tests/test_restore_drill.py`.
Do: backup a scratch instance → wipe → restore → assert byte-equivalent boundary
files; tamper + wrong-passphrase fail closed. Proves the SOS hatch for real data.

## Rules for external agents
1. One lane. Explicit paths only; NEVER `git add -A`; commit via
   `scripts/safe-commit.sh -m "…" <paths>` (it runs pytest).
2. No secrets in code/tests/docs/repo. No RFC1918/private topology in tracked files.
3. No fake data; label specimens; honest empty/unavailable/stale states.
4. Run gates before committing: `uv run pytest --timeout=30` (4 known env failures ok)
   and `uv run personal-world framework validate --json`.
5. If the shared tree won't import due to another lane, verify in an isolated
   `git archive HEAD` copy and say so in your receipt.
6. Do NOT decide these (owner-only): `/` vs `/station` cutover; vault write-gate
   posture; LAN plain-HTTP vs TLS. Flag them, don't resolve them.

## Receipt format (return exactly this)
```
LANE: <A|B|C|D>
FILES: <created/modified>
TESTS: <command → result>
GATES: pytest / framework-validate results
UNVERIFIED: <anything you could not verify, honestly>
NEEDS-OWNER: <any owner-decision you hit>
```
