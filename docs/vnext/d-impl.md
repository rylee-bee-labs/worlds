# d-impl — build record for build-plan Steps 1–5

**Status: draft branch, source change only.** Authority: Rylee, 2026-10-15, Stage D card: "Build all three as the
plan describes" (items A, B, C). No deploy, PR or publish was run. The contract is not amended.
**Real `pytest` and `fastapi` are not available in this sandbox: the suite was NOT RUN.** CI's result is the evidence.

## Per step

| Step | Change | Proof |
|---|---|---|
| 1 | `Request.provenance` (`owner` default) and `Request.verified` (`False`), `models.py:257`–`:258` | `tests/worlds/test_models.py:91` |
| 2 (A) | `Auth.scope: list[Id] \| None = None`, `models.py:114`; `None` = legacy unscoped, `[]` = allows nothing | `test_connect_proof.py:221`; `test_models.py:99` |
| 3 (C) | `models.scope_allows` decides at the call site (`send_scoped`, used by `dispatcher.py`, `runner.py`, `room0.py`, `companion.py`); `confined_request(in_scope=…)` only enforces the verdict in `_prepare` (`confinement.py:598`) before `resolve_within`: out-of-scope → `auth_failed`, no DNS, no dial. A request's capability is the `<name>` half of its id `<provider>.<name>` | `test_connect_proof.py:236` (out of scope, `lookups == []`, no dial), `:251` (in scope still resolves) |
| 4 (B) | `Action.state` closed enum, default `adopted`, `models.py:476` | `test_connect_proof.py:358`; `test_models.py:107` |
| 5 (B) | `dispatcher.py:212` (`can_see`: agents need `adopted`), `:223` (`request_authorization` refuses a non-adopted action for everyone incl. owner), `:343` (`_consume` refuses a non-adopted action, so an earlier approval cannot run) | `test_connect_proof.py:365` |

Backward compatibility: a file omitting the new fields reads as `scope=None`, `state="adopted"`, `provenance="owner"`,
`verified=False`. `action_version` (`models.py:491`) leaves each new field out of the hash at its default, so
authorizations requested before this change keep their version (`test_models.py:114`).
`tests/worlds/test_config_store.py` was not edited.

Step 5 runtime half: `runner.py` was not changed. It only fetches `Request`s as reads and never reads an `Action`;
the runtime refusal is the dispatcher's `_consume` (`dispatcher.py:343`), the only place an action is dispatched.

## The five pins

| Pin (was) | Now | Status |
|---|---|---|
| `:220` auth scope exists | `test_connect_proof.py:221` | plain test |
| `:226` unscoped is labelled | `test_connect_proof.py:228` | **still `xfail(strict=True)`** — see below |
| `:234` out of scope fails before DNS | `test_connect_proof.py:236` | plain test (now builds the provider with `scope=["health"]`; the old body had no scope, which cannot be out of scope under "None = unscoped") |
| `:341` proposed action can exist | `test_connect_proof.py:358` | plain test |
| `:347` proposed action inert | `test_connect_proof.py:365` | plain test (replaces the placeholder body; needs `fastapi`, so it skips without it) |

Also edited: `test_c3_today_a_credential_applies_to_every_request_of_the_provider` (`:193`) asserted
`"scope" not in Auth.model_fields` and that `confinement.py` contains no "scope"; both are false by design now. It asserts
`scope is None` and `models.scope_allows` is true for every path instead.

### Pin `:226` left strict — reason
It needs the word `unscoped` in the card envelope built by `cards.build`. That envelope is made in
`src/personal_world/worlds/cards.py` (evidence at `cards.py:161`) from `runner.Fetch.as_evidence`
(`runner.py:93`). `cards.py` is outside this task's scope, the label itself is build-plan §7 Q2 (undecided), and putting
it in `runner.py` would not be a Step 5 runtime need. Not widened.

## Checks run here
- `python3 -m compileall -q src tests` → exit 0.
- Stand-in script (stdlib + pydantic, outside the repo) calling `confined_request` with a recording resolver:
  scope `["health"]`, id `synth.other` → `auth_failed`, 0 lookups; `synth.health` → 1 lookup; `None` → 1 lookup;
  `[]` → `auth_failed`, 0 lookups.
- The four new `test_models.py` functions plus the existing `test_action_version_changes_with_destination_and_credential_ref`,
  run by hand under a stub `pytest` → all passed.
- NOT RUN: real pytest; any dispatcher test (`fastapi` missing), including `test_connect_proof.py:365`; ruff; bandit.

## Fixes after the independent review
The reviewer's file is `docs/vnext/d-impl-review.md`, committed on this branch and left unedited.

- **MAJOR-1** `test_models.py` `test_action_version_at_defaults_equals_the_pre_change_hash` rebuilds the pre-change payload
  without the new fields and compares. Bites: with the `state` compat lines removed it fails (observed, run by hand).
- **MAJOR-2** (build-plan §7 Q1 option b; contract §7.2 unchanged). The scope decision moved out of `confinement.py` to
  `models.scope_allows`/`send_scoped`, called at every site that sends (dispatcher, runner, room0, companion). The transport
  has no scope logic: `confined_request(..., in_scope=True)` refuses `auth_failed` on `in_scope=False`, before DNS. A sender
  that predates the kwarg still works, because only a refusal passes it. Bites (observed): transport ignoring the verdict, or
  the call site not passing it, fails `test_c3_out_of_scope_capability_fails_before_any_dns_lookup` (lookups/dials non-empty).
  Room0 and companion requests carry ids like `<p>.room`, which are not capabilities; they take the same verdict as before.
- **MINOR-3** `room0.candidates()` reports `adopted` only when the stored action's `state == "adopted"`. No test added; NOT RUN.
- **MINOR-4** the module docstring and the `:226` xfail reason in `test_connect_proof.py` refreshed; the pin stays strict.
- **MINOR-5** (bite now observed, see "Fix2" below; the "by reading" claim here is superseded) `test_c2_a_state_consume_refuses_a_proposed_action_even_with_a_current_version_authorization` forces the row
  `approved` at the current version, so only the `_consume` state check can refuse. NOT RUN (needs `fastapi`); its bite is by
  reading: deleting `dispatcher.py:343`–`:344` lets that row be consumed.
- **MINOR-2 — Step 8 obligation:** "a scope entry naming no capability is refused rather than ignored" cannot be checked in
  the model (it does not know capabilities). The Step 8 register layer must make that save-time check. Not built here.
- Left alone: MINOR-1 (pin `:226` strict, Q2 undecided) and both NITs.

## Fix2: bite experiment, widened diff, send-path trace

### The `_consume` test bites (observed)
`fastapi` is absent, but `authn.py` imports only `HTTPException` and `Request` from it. Outside the repo I put a stub
`fastapi`, a stub `pytest` (`raises`, `importorskip`, `fixture`, `mark`) and a one-file runner on `sys.path`, and ran the
real test function from `tests/vnext/test_connect_proof.py` under `python3 -I`. This is not real pytest.
- Code present: `PASS test_c2_a_state_consume_refuses_a_proposed_action_even_with_a_current_version_authorization`
- `dispatcher.py:343`–`344` deleted (`if action.state != "adopted":` / `raise NotConsumable(...)`):
  `AssertionError: DID NOT RAISE <class 'personal_world.worlds.dispatcher.NotConsumable'>` (raised from the `pytest.raises` at `test_connect_proof.py:430`).
- Restored with `git checkout`, rerun: `PASS` again. `git status` was clean after the restore.
So the test does protect that check.

### Files touched beyond the original six
Original authorisation named six files; the fix also edited `companion.py`, `runner.py`, `room0.py`, `dispatcher.py`
(`dispatcher.py` also for Step 5), and, from this run, `connect_routes.py` and `reference_provider.py`. Why: option (b) puts the verdict in
`models.send_scoped`, and the transport only enforces it, so **every** caller of a sender has to call `send_scoped`.
Per site (diff `22faa9c~1..HEAD`): `companion.py:349`, `runner.py:272`, `room0.py:358`, `dispatcher.py:385` each changed one line,
`self._send(p, r, effect=…)` → `send_scoped(self._send, p, r, effect=…)`. Behaviour is unchanged except an out-of-scope
capability now gets the Step 3 `auth_failed` refusal (an in-scope or unscoped call passes the same arguments as before).
One extra change in `room0.py`: `candidates()` reports `adopted` only when `state == "adopted"` (MINOR-3), not a send change.

### Send-path trace (the question a previous run left open)
Search: `grep -rn "scope_allows\|send_scoped\|confined_request\|_prepare" src` plus every `send(`/`self._send(` call.
| Path | Reaches `_prepare`? | Scope verdict |
|---|---|---|
| `dispatcher.py:385`, `runner.py:272`, `room0.py:358`, `companion.py:349` | default sender is `confined_request` → `_send` → `_prepare` | `send_scoped` |
| `server.py:140` | passes `confined_request` unless `send_override` (tests/dev) | n/a |
| **`connect_routes.py:130` (`/api/connect/try`)** | yes, default `confined_request` | **MISSED**: it called `send(provider, request, effect="read")` directly, so an out-of-scope capability reached DNS and the socket. **Fixed** to `send_scoped(...)`. Owner-only route, read effects only, but it breaks condition 3 as written |
| `reference_provider.reference_send` (`:508` `send`, `:605` `_session_send`, `:685` `_grant_send`) | **no**: it opens its own path (`_exchange`, login, token fetch) and never reaches `confined_request`/`_prepare` | none, and it took no `in_scope` kwarg, so an out-of-scope verdict raised `TypeError` instead of refusing. **Fixed**: `send` takes `in_scope=True` and returns `auth_failed` (`pre_send`) first, before any socket; `_session_send`/`_grant_send` are only reachable from `send`, so they are covered |
`reference_send` is TEST-ONLY, loopback-literal only, but `dev.py:114` wires it as `send_override` in dev mode, so it was a real path.
No other sender exists in `src` (`httpx` and `socket` appear only in `confinement.py`; `dispatcher.py` imports `socket` for the host name).
Both fixes use only models-level `send_scoped` and an additive kwarg; no contract text changed.

Tests: new `test_c3_the_reference_sender_honours_an_out_of_scope_verdict_before_any_socket`. Observed under the stub runner: with the
`in_scope` check replaced by `if False:` it fails (`AssertionError` on `auth_failed`); restored, it passes. **No test was added for the
`connect_routes.py` fix** (needs real `fastapi`); it is a one-line change verified by reading and compile only.

### Checks run (stub runner, not real pytest)
All 16 of the 19 `tests/vnext/test_connect_proof.py` functions that take no fixture or `tmp_path` passed under the stub runner;
the 3 others take the `world` fixture (`:81`, `:155`, `:229`, the last being the xfail-strict pin) and were NOT RUN. Real pytest, `tests/worlds/*` (including `test_config_store.py`): NOT RUN.
`python3 -m compileall -q src tests` → exit 0.

### d-ci-fix: the two room/0 guard failures
CI: `test_c2_room0_the_state_proposed_pins_are_strict_and_the_gap_is_still_real` and `test_c3_room0_the_scope_pins_are_strict_and_the_gap_is_still_real` failed. They are guards, written before `Auth.scope` / `Action.state` existed, asserting those pins were still strict xfails. Steps 1-5 flipped four of five pins to plain tests, so the guards were out of date. The code was not wrong.

Changed `tests/vnext/test_room0_proof.py` only:
- The c2 guard now asserts both `Action.state` pins are plain tests (present, no decorator at all, so no xfail and no skip) and that `state` is in `Action.model_fields`.
- The c3 guard asserts the `scope_exists` and `out_of_scope_before_dns` pins are plain, that `test_c3_unscoped_is_labelled_wherever_it_appears` is still `xfail(strict=True)`, and that `scope` is in `Auth.model_fields`.
- The two test names were changed because they asserted the opposite of what they now check.
- **The brief said to keep a negative control for a relaxed pin. None existed in this file** (searched for "relax" and "control"), so I added one: `test_c3_room0_a_relaxed_or_dropped_pin_would_be_detected` feeds the helper a strict, a relaxed and a missing pin. That is an addition, not a preservation.
- I removed the old `"scope" not in confinement source` assertion. It is false now that the scope check exists.

Observed: a stdlib-`ast` check, run outside pytest, shows all four flipped pins are present and undecorated, the label pin is `(strict=True, raises=None)`, and the control inputs return `(True, True)`, `(False, False)` and `(False, False)`. Compileall exit 0.
**NOT RUN:** real `pytest`, so I have not seen the guards pass or the four flipped pins pass. Whether the flipped pins pass is what the rest of the suite shows, and I did not observe it.
