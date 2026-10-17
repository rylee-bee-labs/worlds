# HANDOFF — Continuous-Improvement Swarm Pass, 2026-09-16

Lead session: this one. Findings came from a full surface audit
([`HANDOFF-SURFACE-AUDIT-2026-09-16.md`](./HANDOFF-SURFACE-AUDIT-2026-09-16.md))
plus 8 parallel audit lanes (security, correctness, simplification,
performance, API/CLI, Station, tests, docs-truth). Every finding was
verified against live code before fixing; nothing counted on handoffs.

**Companion/input pass:** the 20-fix swarm brief
(`PROJECT WORLDS — 20-FIX SWARM PASS`) merged with the surface audit.

## Summary

| | count |
|---|---|
| Findings found | 66 (SEC 8 · COR 12 · SIM 10 · PERF 6 · ACTION 5 · STA 5 · TEST 11 · DOC 10) |
| Fixed + tested in this pass | **37** |
| Deferred with reasons | 21 |
| Refuted/not-confirmable | 8 (removed-SPA-era or superseded by redaction already landed) |
| Regression tests added | 33 new tests across 5 test files (+3 new files) |
| Suites | backend `1172 passed, 11 skipped` (was 1134 pre-pass) · `framework validate` 0 violations · Station e2e `25 passed, 1 skipped` |

## Commits landed

- `e82c818` — fix: source-control history tool (`TOOL-030`) + redact private topology + surface truth (pre-swarm launcher)
- security lane — `security: fail-closed step-up header grant, loopback-guarded setup writes, hardened probe URLs, 0600 session/env files` (SEC-01/03/04/06/08; 11 files)
- correctness lane — `fix: media engine construction, journal/JSON robustness, scheduler durability, anthropic tool loop; perf + dead-code cleanup` (COR-01..12 subset, PERF-02/04, SIM-01/02/04; 14 files)
- truth/testing lane — `truth + testing: manifest chat-history row, Station copy/a11y fixes, docs contradictions, public-safety gate widened, real-app backup test` (ACTION-01, STA-01..04, DOC-01/02/03/04/06/07/08/09, TEST-01/12; 13 files)
- `9202778` + security lane 4 — `vault secret reads true-loopback person-only; principal ids validated against identity safe pattern` (SEC-02, COR-08)

## Findings table (fixed)

State vocabulary: HIGH/MED/LOW, V=verified before fix, T=regression test added.

| ID | Sev | Area | Files | Issue | Resolution |
|---|---|---|---|---|---|
| SEC-01 | High | auth | api.py `_step_up_authorized` | Any client could self-elevate via `X-PW-StepUp: 1` with no proxy verification | Header grant now requires `X-PW-Proxy-StepUp-Secret` matching env `PW_PROXY_STEPUP_SECRET` (timing-safe); unset env ⇒ denied. D1–D3 session/loopback semantics untouched. Docs + manifest updated |
| SEC-02 | High | secrets | api.py `vault_get` | Non-loopback ("private IP") accepted for secret-value reads; agents could read values | True-loopback only (unified with `_is_true_loopback`) + person-only |
| SEC-03 | Med | auth | api.py setup, setup_wizard | Unauthenticated network takeover of a fresh instance / FORCE_SETUP re-open | First-run WRITES loopback-only; state reads stay public |
| SEC-04 | Med | SSRF | api.py `_test_adapter` | Arbitrary-URL fetch, redirects followed, Plex token in query string | http(s) absolute-only, redirects refused, token moved to header; private-IP allowlist follow-up documented |
| SEC-06 | Low | secrets | auth.py SessionStore | Plaintext-perms session file, silent corrupt-load | Atomic 0600 saves + logged warning; 5 durability tests |
| SEC-08 | Low | secrets | api.py setup | `.env` written without 0600 | O_EXCL 0600 + chmod |
| COR-01/02 | Crit | media | native_media.py, api.py, tool_registry.py | Adapter objects passed where connection dicts expected → every `/api/media/*` 500s once any adapter configures; inline-credential heuristic rejected everything (contradicting docstring) | Canonical `build_media_engine_from_connections` is now the sole construction path; inline creds accepted, `vault://`/`${VAR}`/placeholder refs still refused |
| COR-03 | Med | journal | journal.py `by_ts` | Non-ISO `ts` → 500 on supersede/history | Guarded parse → honest `ok:false` envelope |
| COR-04 | High | api | api.py reconciler GETs | Required JSON bodies on GETs → always 500 | Defensive body reads |
| COR-05 | High (data loss) | scheduler | scheduler.py | No lock, non-atomic save, silent corrupt-load → reminders could be wiped | RLock + atomic save + logged load failure |
| COR-06 | High | chat | chat_registry.py | Anthropic tool loop violated protocol (no `tool_use` replay) → provider 400s | Assistant turns rendered as tool_use blocks; mapping test |
| COR-08 | Med | identity | api.py create endpoints | Unicode principal ids accepted → permanent 500s on scoped routes; dotted ids wrongly rejected | `fullmatch` of `identity._SAFE_PRINCIPAL_ID` |
| COR-09 | Med (observability) | tools | tool_registry.py `invoke` | Handler bugs masqueraded as `invalid_args`/`unavailable` with no logging | Logged (exception level in generic branch) |
| COR-10 | Med | proposals | tool_registry.py `execute` | approved-check + status flip outside lock → double-execute window | Under `self.lock`; double-execute refused |
| COR-11 | Low | themes | theme_pack.py, api.py | Unknown theme 200'd as default pack (dishonest) | `get_or_none` + 404 |
| COR-12 | Low | setup | api.py | `/api/setup/status` disagreed with `/healthz` on `FORCE_SETUP=1` | Shared `setup_needed()` predicate |
| SIM-01 | — | media | native_media.py | Duplicate construction paths | Consolidated (see COR-01/02) |
| SIM-02 | — | api | api.py | Dead twin branches in approve/reject | Deleted |
| SIM-04 | — | cleanup | cli.py, api.py | `choice_map=None`, unused `UserAction`, shadowing re-import, `_capability_description` (zero callers), no-op import, stale SPA comment | Deleted/fixed |
| PERF-02 | Low | perf | api.py apps | World+registry built per call then discarded | `_user_paths` only |
| PERF-04 | Low | perf | api.py | `n` unbounded on journal read | Clamped 1..500 (chat-history precedent) |
| ACTION-01 | Low | manifest | api_manifest.py | Live `/api/chat/history` not in curated table | Curated row `API-010-history` |
| STA-01 | Low | truth | station/journal-view.js | Binding comment pointed at nonexistent route | Corrected to API-005/006 |
| STA-02 | Low | truth | station/interests-view.js | Disclosure claimed persisting writes then contradicted itself | Honest target wording |
| STA-03 | Low | a11y | station/search.js | Focus trap didn't exclude `tabindex="-1"` | Parity filter added |
| STA-04 | Low | a11y | station/station.js | `mood` special-cased but absent from PREFS (applier never applied it) | Added |
| TEST-01 | Med | tests | test_worlds_backup.py | Whole-world backup routes only tested behind a stub gate; stale "not wired" comment | Real-`create_app` test (401 without token / 200 honest envelope with) + comment fixed |
| TEST-12 | Med | tests | test_public_safety.py | Topology scan skipped `.project/*.md` (the exact class of DOC-leak) | Scans all tracked `.project/**/*.md` for RFC1918 literals + FORBIDDEN_HOSTS; passes clean |
| DOC-01/02/03/04 | Med | truth | ARCHITECTURE.md, OPERATIONS.md | `/api/chat/test` "unauthenticated" (auth'd since P0); removed rollups route listed; vault set/delete step-up unreported; proposal store wrongly called instance-global | All aligned to code |
| DOC-06 | Low | truth | QUICKSTART.md | Claimed e2e/axe gate "still to-do"; it is the standing gate | Real gates documented |
| DOC-07 | Med | truth | SECURITY.md | "single-user" + Vite framing (multi-principal shipped; SPA removed) | Updated |
| DOC-08/09 | Low | truth | .project/CURRENT.md, REPOSITORY-INVENTORY.md | `PW_FRONTEND_DIST` taught as canonical (deleted 2026-09-16) | Superseded notes; vars moved to inert bucket |
| TOOL-030 | High | tools | tool_registry.py | `inspect_source_control_history` imported nonexistent `source_control.history` | Fixed to `repository_history` + name→path resolution; `TestHistoryToolRegression` (pre-swarm commit `e82c818`) |

Also pre-swarm in `e82c818`: private-topology redaction in `.project/CURRENT.md` and `docs/AUTHELIA-CLIENT-SNIPPET.md` (values not restated), ORPHANS.md audit entries.

## Verification (exact)

- `uv run pytest --timeout=30` → **1172 passed, 11 skipped** (per-lane intermediate gates: 1152 → 1167 → 1169 → 1172, all green before commits)
- `uv run personal-world framework validate --json` → violations count 0 (after each lane)
- `cd frontend && npm run test:e2e` → **25 passed, 1 skipped** (after Station TS/JS changes)
- Security specifics: 6 mocked `TestAdapterProbeHardening` tests; 4 step-up negative tests; loopback-only setup/provider tests; vault remote/agent 403 tests; real-app `/api/worlds/backup` wired-route test.

## Deferred findings (with reasons)

- **SEC-05 (agent scopes declared, never enforced)** — Med. Enforcement semantics (which default scopes agents get, whether `/api/chat` needs `read`) is an owner decision; a naive `require_scopes` would lock existing chat agents out. Needs a scope-schema decision first.
- **SEC-07 (token prefixes in users.json)** — owned by the in-flight identity lane (`identity.py` was dirty during this pass with session-hardening work); must not be edited here.
- **COR-07 (multi-mode: world writes & exports bypass per-principal scoping)** — real, but spans exports/status/daily/intent/fact/policy semantics; needs a coherent multi-mode pass, not a spot fix.
- **SIM-03** (five copies of journal-target helper), **SIM-05** (status vocabulary: `fail()` default `unhealthy` off-vocabulary; `_test_adapter` statuses; legacy-vs-dispatch exit codes — see ACTION-03), **SIM-06/SIM-08/SIM-09/SIM-10** — all mechanical but touch many envelope/status call sites while the other lane holds `identity.py`; landing after that lane merges keeps diffs reviewable.
- **PERF-01/03/05/06** (world+registry mtime caching; one-pass journal streaming; `status_all` TTL cache; per-delivery `_state()` for reminders) — verified real, but caching world state is multi-writer-sensitive and deserves its own dedicated lane with concurrency tests.
- **ACTION-02/03/04/05** — manifest-wrapping drift (`auth status` binding), CLI exit-code vocabulary, help text, legacy `journal` calm-view alignment: each is a behavior-visible CLI change; cheap individually, best batched as a single CLI-parity lane.
- **STA-05** (chat dock Escape behavior) — minor; the dock intentionally has no trap; prefer one decision from the companion a11y pass.
- **TEST-02/03/04/05/06/07** (parametrized step-up sweep per route; two-directional manifest gate test; fake-client vault guard pumped through HTTP; export-route unauth sweep; multi-mode vault semantics pin; cross-principal proposal lifecycle over HTTP) — valuable; several overlap `SEC-04`/`SEC-01` test surfaces that just changed, so a dedicated auth-test lane should write them once, against the now-final gates.

## Best next swarm targets (small, high-value)

1. `SIM-03`: route all journal-target sites through `_journal_target` (mechanical, ~10 sites).
2. `SIM-05` + `ACTION-03`: one canonical status/exit vocabulary spec + vocabulary pin test.
3. Parametrized negative-403 sweep over every step-up-gated route (TEST-02) — after the security commits land on `origin/main`.
4. Multi-mode world-write scoping (COR-07) — owner decision, then `_state_for`-style pass with a two-principal test.
5. Agent scope enforcement (SEC-05) — needs scope-default decision.
6. `PERF-01`: mtime-keyed world cache + single connections.json parse per `build_registry` (with multi-writer test).
7. Journal `current_events` single-pass + `recent` streaming (PERF-03).
8. 5s TTL cache on `status_all` for the Projects surface (PERF-05).
9. Identity lane's follow-on: `SEC-07` token_prefix handling, once `identity.py` merges.
10. Private-IP policy for adapter probes (SEC-04 follow-up): explicit allowlist flag semantics with the owner.

## Honest notes

- The repo's RFC-vacuum ruff/preexisting lint noise was left untouched (not a repo gate).
- `.agent/STATE.md` (retired pointer) may still describe the old step-up header rule — retired pointer routes to `.project/CURRENT.md`, now accurate.
- The other lane's WIP (`identity.py`, `providers/adapters.py`, `tests/test_identity.py`) is intentionally still uncommitted in this checkout; it predates and is independent of this pass.
