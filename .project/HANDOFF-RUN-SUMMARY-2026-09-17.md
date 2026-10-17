# HANDOFF — Session Run Summary, 2026-09-17

One combined handoff for everything this run accomplished. Detailed
evidence lives in the companion files; this is the entry point.

**Repo state:** `main` @ `f4b063f` (local; `origin/main` was `3accaee`
when the run started — commits have not been pushed by this session).
Still-dirty files `src/personal_world/identity.py`,
`providers/adapters.py`, `tests/test_identity.py` are **another lane's
in-flight work** (session hardening) — deliberately not touched, not
committed by this handoff. Do not absorb them.

**Final gates at close:** `uv run pytest --timeout=30` → **1173 passed,
11 skipped** (1134 pre-run) · `framework validate` → 0 violations ·
Station e2e `cd frontend && npm run test:e2e` → **25 passed, 1 skipped**
· `tests/test_public_safety.py` green over tracked files.

---

## 1. What this run produced (3 phases)

### Phase 1 — Full surface audit
`[HANDOFF-SURFACE-AUDIT-2026-09-16.md](./HANDOFF-SURFACE-AUDIT-2026-09-16.md)`
- Traced every real surface: backend HTTP (~110 routes in 8 families),
  CLI (legacy tree + decision-#19 `do` surface), Station UI (15 of ~110
  endpoints actively called by design), login/setup, providers,
  workers, storage, deploy/scripts, tests, docs truth-routing.
- Ranked unwiring gaps: chat wiring (#1), Station writes, themes
  (`/static/companions` break), prefs sync, projects source-control,
  `/api/projects/status`.
- Found new-vs-registry items: `tool_registry` history ImportError,
  `connections/validate` alias, webfont orphan, memory no-reindex gap,
  private topology in `.project/CURRENT.md`.

### Phase 2 — Security/correctness launcher (`e82c818`)
- **TOOL-030 fixed:** `inspect_source_control_history` imported a
  nonexistent `source_control.history`; now resolves repo name→path via
  the same shape as `/api/source-control/history` and calls
  `repository_history`. Regression tests:
  `tests/test_source_control.py::TestHistoryToolRegression`.
- **Public safety:** redacted duckdns hostname + RFC1918 literal from
  `.project/CURRENT.md`; generic issuer placeholder in
  `docs/AUTHELIA-CLIENT-SNIPPET.md`. Swept all tracked files for the
  values (clean).
- Surface truth: ORPHANS.md updated with the audit (wired vs
  API/CLI-first vs archived/blocked classification preserved).

### Phase 3 — 20-fix swarm pass (`f3afd0e`, `002d13c`, `9202778`,
`4e24123`, `f4b063f`)
Full ledger:
`[HANDOFF-SWARM-IMPROVEMENTS-2026-09-16.md](./HANDOFF-SWARM-IMPROVEMENTS-2026-09-16.md)`.
**66 verified findings → 37 fixed + tested, 21 deferred with reasons.**
Each fix lane ran its own full gates before commit.

## 2. Fixed — by severity

### High security (4)
- **SEC-01** step-up header self-elevation → requires
  `X-PW-Proxy-StepUp-Secret` vs env `PW_PROXY_STEPUP_SECRET`
  (timing-safe); unset env ⇒ denied. D1–D3 session/loopback semantics
  unchanged. **Operator note: reverse-proxy deployments must set the env.**
- **SEC-02** vault secret-value reads: RFC1918/bridge IPs removed →
  true loopback only + person-only (agents 403).
- **SEC-03** first-run setup takeover: `POST /api/setup` and
  setup-wizard writes now loopback-only (state reads stay public).
- **TOOL-030** broken source-control history tool (above).

### Medium security (2)
- **SEC-04** probe hardening: http(s) absolute URLs only, redirects
  refused, Plex token moved out of the query string.
- **COR-08** principal-id validation (`héllo` ids poisoned every scoped
  route) → `fullmatch identity._SAFE_PRINCIPAL_ID`; dotted ids now accepted.

### Data-loss / correctness (7)
- Media routes hard-500 with any configured adapter — canonical
  `build_media_engine_from_connections`; inline credentials honored,
  `vault://`-style refs still refused (COR-01/02 + SIM-01).
- Scheduler could **wipe reminders** on corrupt file — RLock, atomic
  saves, logged load failure (COR-05).
- Anthropic tool loop broken at round 2 → tool_use replay fixed (COR-06).
- Journal garbage-`ts` 500s → honest envelopes (COR-03).
- Reconciler GET endpoints tolerated missing bodies (COR-04).
- Proposal double-execute race → lock around status flip (COR-10).
- Tool invocation errors now logged, not silently masked (COR-09).

### Honesty / truth (11)
Unknown theme 404 instead of default-pack 200 (COR-11); `/api/setup/status`
honors `FORCE_SETUP` (COR-12); curated manifest row for
`GET /api/chat/history` (ACTION-01); Station copy corrections
(journal binding, interests disclosure) + 2 a11y one-liners (STA-01-04);
10 docs contradictions aligned with code — chat/test auth, vault
step-up, per-principal proposals, removed rollups route, real e2e gate,
SPA/Vite-era framing, `PW_FRONTEND_DIST` → inert (DOC-01..09).

### Low security / cleanup / perf (constructed)
sessions.json atomic 0600 + corrupt warnings (SEC-06); setup `.env`
O_EXCL 0600 (SEC-08); journal `n` clamped 1..500 (PERF-04); `/api/apps`
registry-build waste removed (PERF-02); dead code deleted
(SIM-02/04); redundant twin branches removed.

### Test/Docs gates (2 structural)
- Real-app `/api/worlds/backup` wired-route test replacing a stub-gated
 -only test + stale comment (TEST-01).
- `test_public_safety.py` now scans all tracked `.project/**/*.md` for
  topology literals (TEST-12) — passes clean.

## 3. Commits (this run)

| SHA | What |
|---|---|
| `e82c818` | history tool fix + topology redaction + ORPHANS truth |
| `f3afd0e` | security lane (SEC-01/03/04/06/08; 11 files) |
| `002d13c` | correctness lane (media/journal/scheduler/anthropic/proposals/themes/setup + perf + dead code; 14 files) |
| `9202778` | manifest + Station + docs truth + gate widening (13 files) |
| `4e24123` | SEC-02 vault loopback/person-only + COR-08 id validation |
| `f4b063f` | both handoff documents |

All committed via `scripts/safe-commit.sh` with explicit paths; full
pytest ran inside the gate before each commit.

## 4. Deferred (with reasons — full list in swarm handoff)

Owner decisions needed: agent scope enforcement (SEC-05), multi-mode
world-write scoping (COR-07), CLI exit-code vocabulary (ACTION-03),
adapter-probe private-IP policy, vault-per-principal semantics.
Mechanical but multi-call-site: journal helper consolidation (SIM-03),
status vocabulary spec (SIM-05), CLI parity batch (ACTION-02..05).
Perf caching lanes need multi-writer tests first (PERF-01/03/05/06).
More negative-test sweeps (TEST-02..07) should be written once against
the now-final gates.

## 5. Deployment notes for the next agent

1. `PW_PROXY_STEPUP_SECRET`: previously-working `X-PW-StepUp: 1`
   delegation now requires the proxy to inject a matching secret header;
   unset env = header denied (fail closed). Update OPERATIONS guidance.
2. First-run setup writes are loopback-only — document the SSH/port-forward
   path or an operator-approved relaxation if LAN-first-run is needed.
3. Secret-value vault reads no longer accept "private bridge" clients —
   any workflow reading vault values over a LAN host must switch to
   loopback or a person-approved path.
4. Test counts in old docs are historical; re-run gates (the repo
   convention) — current: 1173/11.

## 6. Next concrete actions
1. Run the in-flight identity lane to completion and commit its 3 dirty
   files (not this run's work).
2. Push `main` (6 local commits ahead of `3accaee`).
3. Open the chat-wiring lane (`/api/chat*` ↔ `station/chat.js`) as its
   own swarm lane — the biggest verified product gap.
4. Small: curation review of setup-wizard/worlds-backup routes in the
   manifest; consolidate `/api/connections/validate` alias decision.
