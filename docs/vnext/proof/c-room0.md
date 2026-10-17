# c-room0 proof: Project Home as the contract's room/0, read-only and synthetic

> **Status: DRAFT proof, not deployed.** Synthetic data only: the room is a fixture, the address is the
> shipped `*.lan.example` placeholder (a reserved name that never resolves), the principal is the
> recipe's `your-person-id` placeholder. No network, no real credential, no write path, no owner ask
> during the test. Scope came from the c-room0 card; publishing to the shared gallery is a Claude-side
> action, not this worker's - nothing here is published.
>
> Reads as one suite with the Stage C proof: `docs/vnext/proof/c-proof.md` and
> `tests/vnext/test_connect_proof.py`. Same fixture style, same naming. This file adds the room/0 half.

## Decisions in force (quoted, not paraphrased)

- 2026-10-14 23:30Z Rylee, on the Stage C card: **"After the freeze"**. Scope: read-only end-to-end proof
  against the Connect contract (#329), synthetic data only, never deployed, DRAFT PR only. "No owner asks
  during the test." Her card also rules out auto-merge and any command that would mark a PR ready or merge
  it; this worker runs none of those.
- 2026-10-13 Rylee: "Queue all but offload the work you can so we can use it for benchmarks".
- Sol #147 (advice, 2026-10-13): the read-only Project Home room/0 compatibility checkpoint must finish
  BEFORE any implementation architecture is committed, and it must verify zero-provider, stale/UNKNOWN
  and revoked-connection states.
- 2026-10-15 Claude, answering an [architecture] escalation on this task: "Do not amend the contract ...
  Keep the two proof tests xfail-strict, and put Auth.scope + Action.state ... into the d-plan as
  protected-code work ... the plan only describes it, nothing is built." Concretely for this worker: the
  contract §6.1 promises `Auth.scope` and `Action.state` and `confinement.py` resolves DNS before any
  scope check, so Sol's conditions 2 and 3 CANNOT pass against today's code. `tests/vnext/test_connect_proof.py`
  already pins both with `xfail(strict=True)`; those pins are left exactly as they are - not relaxed, not
  marked passed, and the contract is not edited to match the code.
- 2026-10-16, merging `origin/main` into the Worlds vNext implementation branch (#353): the protected-code
  work the decision above scoped to the d-plan **landed**. `Auth.scope` and `Action.state` now exist and the
  scope verdict is refused before DNS, so the pins that decision describes were flipped - by the
  implementation satisfying the contract, not by relaxing a pin. The two guards in this file's test were
  rewritten to say so: the flipped tests must stay plain, the "unscoped" label pin must stay strict, and a
  negative control proves the guard tells strict from relaxed from removed. The quote above is left exactly as
  it was written.
- Protected invariants this proof binds: local Memory; accessibility floors; zero-provider usability;
  security/consent; no invented status; "external systems keep their own authority (Project Home owns
  operational authority, Companion owns chat, services own data)."

Nothing protected was modified. No protected module is edited anywhere in this change; the tests import
`room0`, `config_store`, `confinement`, `cards`, `runner` and `dispatcher` and call only public seams.

## What this proof is, and is not

The contract (`docs/vnext/connect-contract.md`) is a MOCKUP: no `/api/connect/v1` route exists, and
`Auth.scope` / `Action.state` are fields it *proposes*; they did not exist when this proof was written and
**do exist now**, in the implementation branch this file merged into. So "Project Home is the contract's
room/0" is **partly provable**. This file proves the room/0 read surface as it
exists - `room0.py`, `config_store.py`, `confinement.py`, `dispatcher.py` - across the three states the
card names, and carries the Stage C conditions through: condition 1 fails closed and passes here;
conditions 2 and 3 were pinned strict `xfail` in the sibling file and were **not provable** against the code
of the day - the implementation now closes both, so they run as plain tests and the two guards in this
file assert they STAY plain. The 2026-10-16 revision adds a pin that lives in this file itself: the zero-provider surface is
proven to render, but its missing empty-state explanation is a strict `xfail` here, because no such
words exist in the code. An `xfail` is a gap, not a pass. So this proof does **not** show that Worlds
tells a person why the screen is empty: the server half of contract C6.1 holds (200, `first_run` true),
and the UI's guided start ("Connect your first service") is unbuilt. Tracked in personal-world#357.

## How it was run (read this first)

The sandbox has **no `pytest`, no `fastapi` and no `node`** (commands B, D, F below). Real pytest never
ran. I ran the new file with a throwaway stand-in kept **outside the repo** (`/tmp/room0-shim/run.py`,
which supplies `pytest.raises`, `importorskip`, `mark.xfail(strict=...)`, `tmp_path` and a `fail`, over a
stub `fastapi` exposing only `HTTPException` and `Request` so `authn.py` imports). That is a weaker check
than pytest: it honours strict `xfail` and `raises=`, but it is my own runner. The three `test_c1_room0_*`
tests are dispatcher tests and call `pytest.importorskip("fastapi")` (as the Stage C file does): under
real pytest **without** fastapi they would be SKIPPED, i.e. NOT RUN; with the `test` extra they run for
real. A negative control confirmed the pin-assertion parser sees a relaxed pin as not-strict (strict
`False`), so the pins cannot be silently relaxed.

**Revision 2026-10-16 (codex REQUEST-CHANGES).** The review found state 1 proved only that the service
data was empty; it could not show that Worlds stays usable and *tells the person why* the screen is
empty. The revision adds two tests at the surface the UI reads (`GET /api/boards/home`, wired as
production wires it, `production.py:91`) and re-ran everything with a rewritten stand-in at the same
outside-the-repo path. The stub `fastapi` now also carries `FastAPI`/`Depends`/`Body` and a stub
`TestClient` that calls the registered route handler directly, so the home-board route's real code runs
under the runner - a weaker check than a real HTTP round trip (no middleware, no principal dependency,
no starlette). The bite of both new assertions was verified by negative controls (commands J, K): a
temporarily blanked surface fails the render test, and a temporarily added explanation flips the strict
xfail to XPASS, which fails the run. `src/` was restored byte-identical after each control; no `src/`
or `ui/` file is part of this change.

**This merge (`origin/main` into #353), 2026-10-16.** The test file is the merged one: main's reviewed
room/0 tests (the `home_board` pair above) are kept, and the branch's flipped Stage C guards are kept, so
the suite is the union. Every command and count above is a **pre-merge** run of one side, and two of the
guard test names in those lines (`..._pins_are_strict_and_the_gap_is_still_real`) were renamed by the merge
to `..._pins_are_plain_tests_now_that_the_gap_is_closed` and
`..._pins_are_plain_or_strict_as_the_gap_is_closed_or_open`. The merge environment has no `pytest`, no
`fastapi` and no `ruff`, so **the merged suite was NOT RUN**; the host must run
`python -m pytest -q tests/vnext tests/test_public_safety.py` and `ruff check tests/vnext`. Verified here
instead: both files compile, no conflict marker survives anywhere in `docs/` or `tests/`, and the merged
guards' Stage C test names are exactly the names the merged sibling file defines - all three guard tests, plus the negative
control, pass.

As a signal only (NOT the acceptance test; `pydantic` and `httpx` are present here, `pytest`/`fastapi`/`ruff` are not), the
throwaway stand-in outside the repo at `/tmp/m353-shim/run.py` ran both merged files: `test_room0_proof.py` gave **11 passed**,
3 not runnable (`dispatcher` -> `authn` -> `fastapi`) and 2 SKIPPED by their own `importorskip("fastapi")` - the two
`home_board` tests, so the empty-state pin is NOT RUN here, exactly as it is recorded above - and
`test_connect_proof.py` gave **11 passed, 1 xfailed** (the `unscoped` label pin), 10 not runnable for the same `fastapi`
reason.

## Commands and observed output

| # | Command | Exit | Observed tail |
|---|---|---|---|
| A | `python3 -m compileall -q src tests` | 0 | (no output) |
| B | `python3 -m pytest -q tests/vnext` | 1 | `/usr/bin/python3: No module named pytest` |
| C | `PW_REPO=$PWD python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py` | 0 | `{'passed': 13, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'xpassed': 0}` |
| D | `python3 -c "import fastapi"` | 1 | `ModuleNotFoundError: No module named 'fastapi'` |
| E | `PW_REPO=$PWD python3 -I /tmp/room0-shim/run.py tests/vnext/test_connect_proof.py tests/vnext/test_room0_proof.py` | 0 | `{'passed': 23, 'failed': 0, 'skipped': 0, 'xfailed': 5, 'xpassed': 0}` |
| F | `command -v node; ls ui/node_modules` | 1 | `command -v node` prints nothing; `ls: cannot access 'ui/node_modules': No such file or directory` |
| G | `test -s docs/vnext/proof/c-room0.md && python3 -m compileall -q src tests` | 0 | (no output) |
| H | `PW_REPO=$PWD python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py` (revision) | 0 | `{'passed': 14, 'failed': 0, 'skipped': 0, 'xfailed': 1, 'xpassed': 0}` |
| I | `PW_REPO=$PWD python3 -I /tmp/room0-shim/run.py tests/vnext/test_connect_proof.py tests/vnext/test_room0_proof.py` (revision) | 0 | `{'passed': 24, 'failed': 0, 'skipped': 0, 'xfailed': 6, 'xpassed': 0}` |
| J | bite control: same runner, `PW_K=home_board`, with the home route temporarily made to answer 404 when no board exists | 1 | `FAIL test_room0_zero_provider_home_board_still_renders` / `XFAIL test_room0_zero_provider_home_board_says_why_it_is_empty` |
| K | bite control: same runner, `PW_K=home_board`, with `out["first_run_reason"] = "No services connected yet."` temporarily added to the route | 1 | `XPASS test_room0_zero_provider_home_board_says_why_it_is_empty (strict xfail passed: the gap it named is gone)` |
| L | `python -m pytest -q tests/vnext/test_room0_proof.py` | 1 | `/usr/bin/python: No module named pytest` - the host re-runs this for real |

Per-test lines from H (the whole file as revised; `XFAIL` is the new empty-state pin, not a pass):

```
PASS test_room0_zero_provider_home_board_still_renders
XFAIL test_room0_zero_provider_home_board_says_why_it_is_empty
PASS test_room0_zero_provider_is_empty_and_honest
PASS test_room0_a_card_for_an_absent_source_reads_not_configured
PASS test_room0_a_stale_card_is_never_current
PASS test_room0_last_good_after_a_failure_is_stale_not_live
PASS test_room0_unknown_is_unknown_never_healthy_or_zero
PASS test_room0_a_revoked_credential_is_named_and_not_retried
PASS test_room0_a_removed_provider_is_not_served_from_a_stale_snapshot
PASS test_room0_runs_synthetic_and_read_only_reaching_no_live_project_home
PASS test_c1_room0_a_project_home_answer_without_a_verifier_is_never_approved
PASS test_c1_room0_the_owner_cannot_approve_a_project_home_action_in_worlds
PASS test_c1_room0_a_verifier_that_does_not_confirm_leaves_it_unapproved
PASS test_c2_room0_the_state_proposed_pins_are_strict_and_the_gap_is_still_real
PASS test_c3_room0_the_scope_pins_are_strict_and_the_gap_is_still_real
```

(Command J was run twice. The first run, before the explanation pin was tightened, also XPASSed it -
an error body's `detail` string was being counted as words - so
`test_room0_zero_provider_home_board_says_why_it_is_empty` now asserts the surface answers 200 before
looking for words. The J line above is the tightened test's output: the render test FAILs and the pin
stays XFAIL, exactly because a blank surface is not an explanation.)

Per-test lines from C (the whole new file):

```
PASS test_room0_zero_provider_is_empty_and_honest
PASS test_room0_a_card_for_an_absent_source_reads_not_configured
PASS test_room0_a_stale_card_is_never_current
PASS test_room0_last_good_after_a_failure_is_stale_not_live
PASS test_room0_unknown_is_unknown_never_healthy_or_zero
PASS test_room0_a_revoked_credential_is_named_and_not_retried
PASS test_room0_a_removed_provider_is_not_served_from_a_stale_snapshot
PASS test_room0_runs_synthetic_and_read_only_reaching_no_live_project_home
PASS test_c1_room0_a_project_home_answer_without_a_verifier_is_never_approved
PASS test_c1_room0_the_owner_cannot_approve_a_project_home_action_in_worlds
PASS test_c1_room0_a_verifier_that_does_not_confirm_leaves_it_unapproved
PASS test_c2_room0_the_state_proposed_pins_are_strict_and_the_gap_is_still_real
PASS test_c3_room0_the_scope_pins_are_strict_and_the_gap_is_still_real
```

Per-test lines from E (both files, so the inherited pins are visible as XFAIL, not quietly removed):

```
... (15 Stage C tests: 10 PASS, 5 XFAIL - see c-proof.md) ...
PASS test_room0_... (all 13 above)
{'passed': 23, 'failed': 0, 'skipped': 0, 'xfailed': 5, 'xpassed': 0}
```

## State 1 - zero-provider: nothing configured at all

Command (filtered to the four zero-provider tests; same stand-in runner as C; the two `home_board` tests
are the 2026-10-16 revision's):

```
PW_REPO=$PWD PW_K=zero_provider python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py
PASS test_room0_zero_provider_home_board_still_renders
XFAIL test_room0_zero_provider_home_board_says_why_it_is_empty
PASS test_room0_zero_provider_is_empty_and_honest
{'passed': 2, 'failed': 0, 'skipped': 0, 'xfailed': 1, 'xpassed': 0}          (exit 0)

PW_REPO=$PWD PW_K=absent_source python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py
PASS test_room0_a_card_for_an_absent_source_reads_not_configured
{'passed': 1, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'xpassed': 0}          (exit 0)
```

**The surface still renders (proven).** The screen a person opens is the React Home, which reads
`GET /api/boards/home` (`server.py:164-175`; production wires the room's `home_items` into it,
`production.py:91`). With zero providers the route answers **200** with the same keys a populated
board answers - `id`, `title`, `items` - plus `first_run: true`; it is never a 404, first run is a
state, not an error (`server.py:173-174`). Observed: `r.status_code == 200`, the three keys are
present, `items == []`, `first_run is True`, and rendering the surface sent nothing (`fx.calls == []`).
So the empty config does not break the front door: the board loads, the screen can be navigated. That
is the "Worlds stays usable" half of the claim, and before the revision it was never asserted - the
test checked only that the service data was empty.

**The surface does NOT say why it is empty (gap, pinned - never claimed checked).** The empty-state
explanation **is missing from the code**:

- the payload's only empty-state marker is the bare boolean `first_run` (`server.py:174`) - no words at
  all, nothing like "no services connected yet";
- the React UI never even reads the flag: `ui/src/fd/types.ts:55-59` (`Board`) has only `id`, `title`,
  `items`, and `ui/src/fd/Home.tsx` never mentions `first_run`, so no guided start renders;
- `docs/rebuild/CONTRACTS.md:161` promises that `first_run` drives "a guided start (one 'Connect your
  first service' card, plus Memory)" - no code implements that promise;
- the only empty-state words an empty Home renders are the generic "Nothing for you right now." and
  "Nothing needs a look. Everything is answering." (`ui/src/fd/Home.tsx`), which never say why the
  screen is empty - and "everything is answering" is not a reason a zero-provider world can give.

Per the review's instruction no explanation was invented in `src/` or `ui/` (and none of those files is
part of this change). Instead `test_room0_zero_provider_home_board_says_why_it_is_empty` pins the gap as
a strict `xfail`: it passes only when the payload carries person-readable words (beyond the board's own
`id`/`title`) or the home UI consumes `first_run`, and a strict xfail that starts passing fails the run
(command K observed exactly that flip). An `xfail` is a gap, not a pass.

What the rest of state 1 observed: with an empty `ConfigStore`, `RoomService.providers()` and `rooms()`
and `home_items()` and `needs()` are all `[]` (`room0.py:467-468`, `:493-500`, `:516-526`, `:528-531`),
`Room0Client.snapshot("project-home")` is `None` because `provider()` rejects a missing id before any
send (`room0.py:303-305`), `home_board_defs` is `None` (`cards.py:366-381`) and no sender call was made
(`fx.calls == []`). Nothing is invented: no "connected", no fabricated card, no error that reads like a
bug. The one explicit word for "there is nothing here" is a card whose source is absent reading
`not_configured` with values `{"text": "unknown"}`, never `0` (`cards.py:126-135`, `:173-178`;
`cards.py:256-288`). **No browser check was run** (command F): the empty-state *screen* is NOT RUN -
what is proven above is the payload the screen reads, plus the source of the UI that would render it.

## State 2 - stale and UNKNOWN

Commands:

```
PW_REPO=$PWD PW_K=stale   python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py
PASS test_room0_a_stale_card_is_never_current
PASS test_room0_last_good_after_a_failure_is_stale_not_live
PASS test_room0_a_removed_provider_is_not_served_from_a_stale_snapshot        (state 3b, matched on "stale")
{'passed': 3, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'xpassed': 0}          (exit 0)

PW_REPO=$PWD PW_K=unknown python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py
PASS test_room0_unknown_is_unknown_never_healthy_or_zero
{'passed': 1, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'xpassed': 0}          (exit 0)
```

**Stale.** A room card whose own `freshness.observed_at` is older than its `stale_after_s` renders
`freshness: "stale"` and never `"current"` (`room0.py:433-434`). An unreachable room keeps its
last-good cards and marks them stale (`room0.py:406-409`), so the envelope reads
`source_state: "unavailable"`, `freshness: "stale"` with `evidence.error_class: "connection"`
(`room0.py:420-447`). Observed: `env["freshness"] == "stale"` in both cases, and the first case keeps
the fact readable (`body` text present) while the *lapsed freshness* is what is flagged. A claim I do
**not** make: the lapsed card's `source_state` is still `healthy` - the room's own status - because
availability and freshness are separate fields (contract §4.3; `room0.py:420-421`). The staleness is
visible in `freshness`; the card is never labelled `current`.

**UNKNOWN.** A room status word room0 does not recognise is carried as `unknown`, never mapped to
`healthy` (`room0.py:390`, `STATE_FOR_STATUS` at `:36`), and the status card's value is the literal text
`"unknown"` (`room0.py:426`). A card whose title/body/freshness cannot be read honestly becomes
`source_state: "degraded"` with every value `{"text": "unknown"}` and no `raw` key - never a fabricated
`0` (`room0.py:428-429`). An unrecognised tone is shown as the neutral `update`, logged
(`room0.py:155-158`). Observed: `status_env["source_state"] == "unknown"` and
`broken["values"]["body"] == {"text": "unknown"}` (no `raw`). **No browser check** - keyboard visibility
of stale/unknown is NOT RUN (command F).

## State 3 - revoked connection

Commands:

```
PW_REPO=$PWD PW_K=revoked          python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py
PASS test_room0_a_revoked_credential_is_named_and_not_retried                 (exit 0)
PW_REPO=$PWD PW_K=removed_provider python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py
PASS test_room0_a_removed_provider_is_not_served_from_a_stale_snapshot        (exit 0)
```

**The revocation that the code can name: the room answers 401/403.** `room0.py:364-365` classifies
401/403 as `auth_failed`; `STATE_FOR_ERROR` maps that to `needs_attention` (`room0.py:37-39`), and
`rooms()` reports `reachable: False` with `error_class: "auth_failed"` (`room0.py:528-531`). Observed:
after a good snapshot, a 403 makes `snapshot.error_class == "auth_failed"` while the last-known cards
are copied forward and marked stale (`room0.py:406-410`), and the card envelope reads
`freshness: "stale"`, `source_state: "needs_attention"`, `evidence.error_class: "auth_failed"` - the
revocation is named and nothing stale is shown as live.

**No silent retry.** A failing room is backed off 30 s doubling to 5 min (`FAIL_BACKOFF_S` at
`room0.py:285`; the "left alone until its back-off ends" branch at `room0.py:311-312`). Observed: a
second `snapshot()` inside the window returned the same failing snapshot with `len(fx.calls)` unchanged -
there is no second send.

**Worlds drops its own reference.** With the provider config removed, `snapshot()` returns `None`
before any send (`room0.py:303-305`), `RoomService.card(...)` returns `None`, and `rooms()` /
`home_items()` are empty; the cached last-good snapshot stays in the client's memory but is never served.
Observed: `client.snapshot == None`, `card == None`, `fx.calls` unchanged after removal. Note
`config_store.py:358-369` refuses a delete while something still references the object - so in
production the request/action files an adopted room action created must be removed first; the read-only
proof removes a bare provider.

**Honest gap.** No room0 surface *names* a revocation as such: there is no room0 revoke/disconnect route
and no `revoked` state in `room0.py`. The contract's endpoints 13-14 and `DisconnectResult` /
`RevocationResult` (contract §3, §4.6) are MOCKUP, and `confinement.py:298` (`_session_forget`) is the
only credential-purge in code - it drops a *held* cookie/token, not a room0 bearer reference. So "names
the revocation" is proven only for the room-says-403 path (`auth_failed`); removing the config makes the
room vanish rather than say "revoked". That is recorded under UNRESOLVED, not papered over.

## Inherited Stage C condition 1 (provable - passes): a Project Home-governed answer fails closed

Command:

```
PW_REPO=$PWD PW_K=c1_room0 python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py
PASS test_c1_room0_a_project_home_answer_without_a_verifier_is_never_approved
PASS test_c1_room0_the_owner_cannot_approve_a_project_home_action_in_worlds
PASS test_c1_room0_a_verifier_that_does_not_confirm_leaves_it_unapproved
{'passed': 3, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'xpassed': 0}          (exit 0)
```

Observed: a room0 provider defaults to Project Home governance (`models.py:203-204`,
`Provider.governed_by_project_home`), and `RoomService.answer` routes a supplied
`project_home_approval_id` into `dispatcher.record_project_home_approval` (`room0.py:598-599`,
`room_routes.py:72`). With no verifier wired - production supplies none, `production.py:95` -
`record_project_home_approval` raises `NotPermitted` on its first statement, **before the write
transaction** (`dispatcher.py:277-278`). Observed in all three tests: `NotPermitted` propagates, the
authorization row stays `pending` with `authority IS NULL`, `executions` is empty, and the write sender
(`writes == []`) is never called - nothing reaches the room. The room action the owner adopts is
`exposed: false`, `approval: "always"`, `idempotency: "required"` (`room0.py:627-628`), so it is never an
agent tool and never a no-approval write. Without a `project_home_approval_id`, the owner's own
`dispatcher.approve` refuses a Project Home-governed operation (`dispatcher.py:268-269`).

**Not run:** the HTTP 403 on the wire. `room_routes.py:75-76` maps `NotPermitted` to `HTTPException(403)`,
but fastapi's `TestClient` is unavailable here, so the 403 is shown at the dispatcher, not over HTTP. A
real Project Home 403 is simulated only by fixtures (the refusing-verifier test); end to end over HTTP
is NOT RUN.

## Inherited Stage C conditions 2 and 3: closed by the implementation, guards flipped

These two tests do not make anything pass by assertion about the feature - they assert the **shape of the
pins themselves**, so a future change cannot quietly paper a gap over. When these conditions were unmettable
the guards asserted "strict xfail + the field really is missing"; the implementation landed, so they now
assert the opposite for the closed gaps and keep the strict requirement for the one gap that is still open:

- `test_c2_room0_the_state_proposed_pins_are_plain_tests_now_that_the_gap_is_closed` - `Action.state` exists
  (d-impl Step 3), so both Stage C tests must exist with **no decorator at all** (no `xfail`, no `skip`), and
  `"state" in Action.model_fields`.
- `test_c3_room0_the_scope_pins_are_plain_or_strict_as_the_gap_is_closed_or_open` - `Auth.scope` and the
  pre-DNS scope check exist, so `test_c3_auth_scope_exists_and_none_is_the_legacy_unscoped_state` and
  `test_c3_out_of_scope_capability_fails_before_any_dns_lookup` must be plain tests too; the label pin
  `test_c3_unscoped_is_labelled_wherever_it_appears` must stay a **strict** xfail, because the word
  "unscoped" still reaches no card envelope and no UI surface.
- `test_c3_room0_a_relaxed_or_dropped_pin_would_be_detected` - the negative control: the parser must read
  a strict pin as strict, a relaxed one as not strict, and a missing function as no pin at all.

**Condition 2 (a proposed Action is inert) - MET by the implementation.** Contract §6.1 proposes
`Action.state` (`connect-contract.md:452`) with a default that leaves every existing action file behaving as
today. `Action.state` now exists (`Literal["proposed", "adopted", "refused", "expired"]`, default
`adopted`, still `extra="forbid"`), and the sibling file proves the inertness directly: a proposed action is
never listed to an agent, `request_authorization` raises `NotPermitted` for agent and owner alike, and
`execute` raises `NotConsumable` - including when an approval is forced current, so the state check and not
version invalidation is what refuses.

**Condition 3 (scoped auth before the network) - MET by the implementation.** `Auth.scope` exists
(`None` = the legacy unscoped state) and the verdict is refused before DNS: `confinement._prepare` checks
`in_scope` before `resolve_within`. The sibling file asserts the ordering on an address confinement accepts,
and that the transport reads no scope itself. **The label half is still open**: the word "unscoped" reaches
no card envelope and no UI surface, and that strict xfail is deliberately not flipped.

## Read-only and synthetic-only

Command:

```
PW_REPO=$PWD PW_K=no_live_project_home python3 -I /tmp/room0-shim/run.py tests/vnext/test_room0_proof.py
PASS test_room0_runs_synthetic_and_read_only_reaching_no_live_project_home
{'passed': 1, 'failed': 0, 'skipped': 0, 'xfailed': 0, 'xpassed': 0}          (exit 0)
```

Every room call across the proof was a fixture call with `effect == "read"` and `method == "GET"`; the
test runs the home/rooms/needs/candidates paths under a guard that replaces `confinement._exchange`,
`confinement._session_send` and `confinement._system_resolver` with a failing stub, so reaching the live
seam would fail the test. `base_url` is `https://project-home.lan.example` - the shipped placeholder
(`config/recipes/project-home/provider.yaml`), a reserved `*.example` name that never resolves - and
`principal_id` is the recipe's `your-person-id`. This covers the paths the proof reaches, not every route
in the app, and it does not claim no other code could dial.

## NOT RUN

- Real `pytest` (commands B, L: `No module named pytest`).
- Real `fastapi`: command D; the three `test_c1_room0_*` tests and the two `home_board` tests ran under
  the shim's fastapi stub and are SKIPPED under real pytest without fastapi (fastapi is a runtime
  dependency, so a normal install runs them for real).
- The HTTP 403 on the wire (`room_routes.py:75-76`) - no real `TestClient`.
- Keyboard visibility of the stale/unknown/retry states and the 390px phone layout - no node, no
  `ui/node_modules` (command F). The repo has `ui/e2e-fd` Playwright specs; I did not run them and make
  no claim about them. Human screen-reader and physical-device checks are NOT RUN until a human runs them.
- Whether the run-2 day-alone test was scored before this started - not checkable from the clone.

## UNRESOLVED

- Real pytest and real fastapi never ran; command C/E/H/I used my own stand-in runner and a fastapi
  stub. Re-run `python -m pytest -q tests/vnext` in an environment with the `test` extra.
- **The zero-provider empty-state explanation does not exist in the code** (2026-10-16 revision): the
  payload carries only the bare boolean `first_run` (`server.py:174`), the UI never reads it
  (`ui/src/fd/types.ts:55-59`, `ui/src/fd/Home.tsx`), and `docs/rebuild/CONTRACTS.md:161`'s promised
  guided start is unimplemented. Pinned strict xfail in the test file; not invented here.
- Conditions 2 and 3 were closed by the implementation this branch carries (d-impl), after the runs above;
  the merged test file's guards were rewritten to match, but no post-implementation pytest run backs them,
  and the merged suite was NOT RUN here (no `pytest`, no `ruff` in this environment).
- The "unscoped" label gap is still open and still strictly pinned: no card envelope and no UI surface says
  it.
- No room0 "revoked" state or route: removing the provider makes the room vanish rather than name a
  revocation; the contract's endpoints 13-14 / `RevocationResult` are MOCKUP. Only the room-says-403
  path names it (`auth_failed`).
- Condition 1 over HTTP (403 from `room_routes.py`) not exercised; Project Home 403 simulated by fixtures.
- Browser/keyboard/390px: NOT RUN (above).

## Return

```
RESULT: done (read-only, synthetic), revised 2026-10-16 for the codex REQUEST-CHANGES and again for this
merge (origin/main into #353). States 1, 2 and 3 proven by command and observed output; state 1 also
proves the person-facing surface (GET /api/boards/home) still renders with zero providers, and pins as a
strict xfail that no explanation of the empty screen exists anywhere in the code (personal-world#357).
Inherited condition 1 passes. Conditions 2 and 3 were unmettable at the time of those runs and are met by
the implementation this branch carries: their pins are plain tests now, and the two guards here assert
they stay plain (the "unscoped" label pin stays strict). The merged suite was NOT RUN here - no pytest,
no fastapi, no ruff in this environment; the host re-runs.

CHANGED: tests/vnext/test_room0_proof.py (15 tests: main's +home_board_still_renders and +the
empty-state explanation pin as strict xfail, plus the branch's flipped Stage C guards and their negative
control; same Stage C fixture style), docs/vnext/proof/c-room0.md (revision section, state 1, new
commands, the conditions-2/3 section and the guards, UNRESOLVED and Return rewritten for the merge). No
src/ or ui/ file is part of this change; the two bite-check edits to server.py were restored
byte-identical. The stand-in runner lives outside the repo at /tmp/room0-shim/run.py and is not part of
the change.

CHECKS: (pre-merge, main's side) python3 -m compileall -q src tests -> exit 0. python -m pytest -q
tests/vnext/test_room0_proof.py -> exit 1 (No module named pytest; the host re-runs). Stand-in runner on
the revised file -> exit 0, 14 passed 1 xfailed 0 failed; on both vnext files -> exit 0, 24 passed
6 xfailed 0 failed. Bite controls -> both exit 1 with the expected FAIL/XPASS (commands J, K), src/
restored after each. (this merge) python3 -m py_compile on both vnext test files -> exit 0;
git grep for conflict markers over docs/ and tests/ -> empty.

EVIDENCE: (pre-merge) observed summaries {'passed': 14, 'failed': 0, 'skipped': 0, 'xfailed': 1,
'xpassed': 0} and {'passed': 24, 'failed': 0, 'skipped': 0, 'xfailed': 6, 'xpassed': 0}; bite controls
'FAIL test_room0_zero_provider_home_board_still_renders' (blanked surface) and 'XPASS
test_room0_zero_provider_home_board_says_why_it_is_empty (strict xfail passed: the gap it named is
gone)' (explanation added); No module named pytest. (merge) both vnext test files byte-compile; no conflict
marker under docs/ or tests/; the guard's Stage C names match the merged sibling file's definitions.
Empty-state gap at src/personal_world/worlds/server.py:164-175 + ui/src/fd/types.ts:55-59 +
ui/src/fd/Home.tsx; contract promise at docs/rebuild/CONTRACTS.md:161.

UNRESOLVED: (1) real pytest/fastapi never ran on either side (stand-in runner + fastapi stub), and the
merged suite was NOT RUN here at all - no pytest, no ruff in this environment; (2) the zero-provider
empty-state explanation does not exist - bare first_run flag, UI never reads it, CONTRACTS.md:161's
guided start unimplemented - pinned strict xfail (personal-world#357); (3) conditions 2 and 3 are closed by
the implementation, but no post-implementation pytest run backs the flipped pins or the rewritten guards;
(4) the "unscoped" label still reaches no envelope or UI surface - strict xfail kept; (5) no room0
revoke route/state - only the room-says-403 path names a revocation; (6) condition 1 over HTTP not
exercised; (7) NOT RUN: keyboard, 390px, real browser, real fastapi.

NEXT: Run `python -m pytest -q tests/vnext tests/test_public_safety.py` and `ruff check tests/vnext` on
the merged tree on the host; add the missing empty-state explanation where a person reads it (words in the
home board payload, or the UI's guided start from first_run as docs/rebuild/CONTRACTS.md:161 promises) and
flip that strict xfail; label the "unscoped" credential and flip the last strict xfail; then run the
phone-390 e2e where a browser exists.
```
