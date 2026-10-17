# Stage C proof: the Connect contract, end to end, synthetic and read-only

> **Status: DRAFT proof, not deployed.** Synthetic data only, no network, no real credential, no write path.
> Scope came from the Stage C card. Rylee, 2026-10-14 23:30Z: "After the freeze".
> Project Home decision 145, 2026-10-13 16:09 CDT: "approve the boundaries; Sol #158 conditions become PRE-PROTOTYPE gates."
> Whether the run-2 day-alone test was scored before this started is **not something I could check from the clone**; the coordinator launched the task.

## What this proof is, and is not

The contract (`docs/vnext/connect-contract.md`) is a MOCKUP. This clone has no `/api/connect/v1` route. `Auth.scope` and
`Action.state`, the two fields the contract proposes, **now exist here** (the Worlds vNext implementation this branch
carries), so conditions 2 and 3 are proven by plain tests instead of by pins, and the sibling `test_room0_proof.py` asserts
that they stay plain - a re-`xfail`ed pin fails that suite. What the contract is still ahead of is the "unscoped" label,
which stays pinned as a **strict `xfail`** naming the missing piece. An xfail is a gap, not a pass.

## How it was run (read this first)

The sandbox has **no `pytest` and no `fastapi`** (`python3 -m pytest` -> `No module named pytest`). Real pytest never ran.
I ran the file with a throwaway stand-in kept outside the repo (`/tmp/shim/run.py`, which supplies `pytest.raises`,
`importorskip`, `mark.xfail(strict=...)`, `tmp_path`, and a stub `fastapi` exposing only `HTTPException` and `Request` so
`authn.py` imports). That is a weaker check than pytest: it honours strict xfail and `raises=`, but it is my own runner. The
dispatcher tests ran under the stub; with real fastapi absent they would be SKIPPED (`importorskip`), meaning NOT RUN.

2026-10-16, after the second-model review (REQUEST-CHANGES) fixed the two condition-3 tests: re-run with a fresh stand-in
at the same distance from the repo (`/tmp/shim-run/run.py`, same surface). Counts unchanged: `{'passed': 10, 'failed': 0,
'skipped': 0, 'xfailed': 5, 'xpassed': 0}`. The out-of-scope xfail now fires as `AssertionError: not refused for scope`
(the request ran to the stubbed sender on an accepted address and was refused by nothing) instead of on a loopback
`confinement_denied`. Real pytest is still missing in the sandbox (no network); the host re-runs it.

**This merge (origin/main into #353), 2026-10-16.** The test file is the merged one: conditions 2 and 3 run as plain tests
against the implementation this branch carries, so the counts and per-test lines recorded below are each side's PRE-merge
run and are **not** a claim about the merged tree - the merged file has fewer xfails and more plain tests. The merge
environment has no `pytest`, no `fastapi` and no `ruff`, so the merged suite was **NOT RUN** here; the host must run
`python -m pytest -q tests/vnext tests/test_public_safety.py` and `ruff check tests/vnext`. What IS verified in the merge
is that the file compiles, that no conflict marker survives, and that the stronger assertions main's review added are the
ones the flipped pins now run.

This environment does have `pydantic` and `httpx`, so as a signal (NOT the acceptance test - it is a throwaway stand-in kept
outside the repo at `/tmp/m353-shim/run.py`, weaker than pytest: no fixtures beyond `tmp_path`, no parametrisation, no
collection) the merged file ran: **11 passed, 1 xfailed** - the xfail is `test_c3_unscoped_is_labelled_wherever_it_appears`,
still a real gap - and 10 tests could not run here at all because `dispatcher` imports `authn`, which imports `fastapi`.

## Commands and observed output

| # | Command | Exit | Observed tail |
|---|---|---|---|
| A | `test -s docs/vnext/proof/c-proof.md && python3 -m compileall -q src tests` | 0 | (no output) |
| B | `python3 -m pytest -q tests/vnext` | 1 | `/usr/bin/python3: No module named pytest` |
| C | `PYTHONPATH=src python3 /tmp/shim/run.py tests/vnext/test_connect_proof.py` | 0 | `{'passed': 10, 'failed': 0, 'skipped': 0, 'xfailed': 5, 'xpassed': 0}` |
| D | `python3 -c "import fastapi"` | 1 | `ModuleNotFoundError: No module named 'fastapi'` |
| E | `command -v node; ls ui/node_modules` | 1 | `ls: cannot access 'ui/node_modules': No such file or directory` |

Per-test lines from C:

```
PASS test_journey_empty_to_disconnected_and_still_usable
PASS test_c4_a_write_request_is_refused_before_the_sender
PASS test_c4_the_confinement_seam_refuses_a_mutating_read_effect
PASS test_c3_today_a_credential_applies_to_every_request_of_the_provider
PASS test_c3_an_unresolvable_reference_sends_nothing
XFAIL test_c3_auth_scope_exists_and_none_is_the_legacy_unscoped_state
XFAIL test_c3_unscoped_is_labelled_wherever_it_appears
XFAIL test_c3_out_of_scope_capability_fails_before_any_dns_lookup
PASS test_c1_project_home_without_a_verifier_is_not_approved_and_never_runs
PASS test_c1_a_project_home_refusal_leaves_the_action_unapproved
PASS test_c1_a_verifier_that_fails_hard_also_leaves_it_unapproved
PASS test_c2_an_unexposed_action_is_inert_for_an_agent_directly
PASS test_c2_an_unexposed_action_is_inert_through_other_paths
XFAIL test_c2_a_state_proposed_action_can_exist
XFAIL test_c2_a_state_proposed_action_is_inert_at_dispatcher_and_runtime
```

## The journey

`test_journey_empty_to_disconnected_and_still_usable` (command C, PASS): empty store -> provider with
`secret_ref: env:SYNTH_CONNECT_TOKEN` (the value is set only in the process env; the test asserts the YAML on disk holds the
reference and not the value) -> one card `healthy/current` -> timeout gives `unavailable/stale` with last-good values kept ->
unmapped status gives `unknown`, a missing field is `{"text": "unknown"}` (never 0) -> same read again recovers to
`healthy/current` -> `valid_link` keeps `/rooms/synth`, drops `https://elsewhere.example/` and `//elsewhere.example/` ->
delete of the provider is refused while referenced (`ConfigInvalid`), then board, card, request, provider are removed ->
store empty, `home_board_defs` is `None`, no further sender call, and a new connection renders again. The secret value appears in
no envelope; only the reference reached the sender.

Limits of that proof: the "retry" is the card service re-reading (`ttl_s: 0`), not `Dispatcher.request_retry`, which is the
write path and is out of scope. "Link out" is proven only for `room0.valid_link`, the one link rule in code; no card field
type renders a link. The contract's own `SourceState` has a `stale` value; the code expresses stale as `freshness: stale` with
`source_state: unavailable`. That is a naming difference to settle, not a failure.

## Condition 1: Project Home approval fails closed

Commands: C. Tests: `test_c1_project_home_without_a_verifier_is_not_approved_and_never_runs`,
`test_c1_a_project_home_refusal_leaves_the_action_unapproved`, `test_c1_a_verifier_that_fails_hard_also_leaves_it_unapproved`
(all PASS, exit 0, under the fastapi stub). Observed: with no verifier, a verifier returning False, and a verifier raising
`PermissionError("403 from Project Home")`, the authorization stays `pending`, `execute` raises `NotConsumable`, and the sender
is never called. The owner's own `approve` on a Project Home-governed provider raises `NotPermitted`.
**Not run:** the HTTP layer. `room_routes.py` maps `NotPermitted` to 403, but I did not exercise it because fastapi's
`TestClient` is unavailable here. The 403 is shown at the dispatcher, not on the wire. A real Project Home 403 is not simulated
end to end either; the verifier fixtures stand in for it.

## Condition 2: a proposed Action is inert

**Met by the implementation this branch carries, and no longer pinned** (was "not proven as written" when the two strict
xfails recorded the gap). `Action.state` exists (`Literal["proposed", "adopted", "refused", "expired"]`, default `adopted`,
`extra="forbid"`), so `..._can_exist` is now a plain test: `state="proposed"` validates, the default is `adopted`, and an
unknown state still raises `ValidationError`. `..._is_inert_at_dispatcher_and_runtime` rewrites an approved action's file as
`state=proposed` (keeping `exposed: true` on purpose) and proves it is inert at both seams: it is never listed to an agent,
`request_authorization` raises `NotPermitted` for agent *and* owner, and `execute` raises `NotConsumable`. A third test forces
a current-version approval so version invalidation cannot be the thing that refuses, and still gets `NotConsumable, match="not
adopted"` - the state check itself, at runtime. Nothing was ever sent (`fx.calls == []`, no `executions` row).

The proxy that was proven before the implementation still holds, as the contract (§6.1) cites for it: an `exposed: false`
action. Direct: an agent's `request_authorization` raises `NotPermitted` and `list_actions` is empty. Indirect: the agent's
`execute` on the owner's pending authorization raises `NotPermitted` and `request_retry` on an unknown execution raises
`BadRequest`; the authorization stays `pending`, sender never called. I did not test the runtime (`Runner`) side of a proposed
action: it has nothing to act on.

## Condition 3: scoped auth before the network, and "unscoped"

**The scope half is MET by the implementation this branch carries, and no longer pinned** (was "not met in code", with three
strict xfails, before it). `Auth.scope` exists (`list[Id] | None`; `None` is the legacy unscoped state, and a non-id entry still
raises `ValidationError`). The verdict is a decision about capabilities, so it is made at the call site
(`models.scope_allows`, `models.send_scoped`) and handed to the transport as `in_scope`; `confinement._prepare` refuses it at
`confinement.py:598`-`:600`, **before** `resolve_within` at `:602`, so an out-of-scope capability costs no lookup and no bytes.
Observed by the tests: `test_c3_out_of_scope_capability_fails_before_any_dns_lookup` asserts `auth_failed`, `lookups == []` and
nothing sent, on an address confinement ACCEPTS (a `lan` provider, synthetic private `10.9.9.9` <!-- pw-safety: synthetic -->,
with the credential available) so address classification can no longer mask the ordering - a scope check that lands only AFTER
DNS keeps the test red on the `lookups` assertion.
`test_c3_the_transport_enforces_the_verdict_it_is_given_and_does_not_decide_scope` shows the transport reads no scope: a call
given `in_scope=False` is refused and never looks anything up, while a call given the verdict goes; and
`test_c3_an_in_scope_capability_still_reaches_dns` shows an in-scope capability still reaches DNS.
`test_c3_the_reference_sender_honours_an_out_of_scope_verdict_before_any_socket` covers the reference sender, which has its own
network path and does not reach `confined_request`: it takes the verdict too, refuses out of scope as `auth_failed` before any
socket, and does not refuse an in-scope request for scope.

Main's review strengthened the unscoped-credential observation, and that strengthening is kept: on an accepted address with the
dial functions stubbed, `test_c3_today_a_credential_applies_to_every_request_of_the_provider` proves BOTH requests of an
unscoped provider reached the sender and EACH carried `Authorization: Bearer <value>` (bite-checked 2026-10-16: an unavailable
credential never reaches the sender, an unattached one arrives bare, and the test fails on both breaks and recovers when
restored), while `scope_allows` allows every request of that provider. `test_c3_an_unresolvable_reference_sends_nothing` shows
an unresolvable reference dials nothing.

**The label half is still a gap: one strict xfail.** The word "unscoped" occurs in no card envelope (`cards.build`) and no UI
surface (it appears only in the contract and a history doc), so a legacy no-scope credential is not labelled anywhere a person
reads. `test_c3_unscoped_is_labelled_wherever_it_appears` stays `@pytest.mark.xfail(strict=True, ...)` naming that piece
(build-plan Q2), and a sibling test asserts it is still strict, so relaxing it fails the suite.

## Condition 4: read-only end to end, keyboard, 390px

Read-only: PASS (command C). Every sender call across the journey was `effect="read"`, `GET`. A `POST` request behind a card is
refused as `confinement_denied` with zero sender calls, and the confinement seam refuses a `DELETE` under a read effect before
DNS. This covers the paths the proof reaches, not every route in the app.

**NOT RUN:** keyboard visibility of the stale, unknown and retry states, and the 390px phone layout. No node, no
`ui/node_modules`, no browser in this sandbox (command E). The repo has a `phone-390` Playwright project under `ui/e2e-fd`; I did
not run it and make no claim about it.

## RESULT / CHANGED / CHECKS / EVIDENCE / UNRESOLVED / NEXT

RESULT: partial. Condition 1 proven at the dispatcher only; condition 4 read-only proven, browser half NOT RUN. Conditions 2 and 3 were NOT met when this file was written and are met by the implementation the branch carries: `Action.state` and `Auth.scope` exist and the scope verdict is refused before DNS, so those five pins are plain tests now and one strict xfail (the "unscoped" label) remains.

CHANGED: `tests/vnext/test_connect_proof.py` (new; the repo has no `tests/vnext`, and the existing `tests/worlds` layout needs relative imports from its own conftest, so this stands alone), `docs/vnext/proof/c-proof.md` (new). No protected code touched.

CHECKS: A `test -s ... && python3 -m compileall -q src tests` exit 0. B `python3 -m pytest -q tests/vnext` exit 1 (no pytest installed). C stand-in runner exit 0, 10 passed 5 xfailed 0 failed.

EVIDENCE: `{'passed': 10, 'failed': 0, 'skipped': 0, 'xfailed': 5, 'xpassed': 0}`; `No module named pytest`; `No module named 'fastapi'`.

UNRESOLVED:
- Real pytest and real fastapi never ran; command C used my own stand-in runner and a fastapi stub. Re-run `python3 -m pytest -q tests/vnext tests/test_public_safety.py` in an environment with the `test` extra; the dispatcher tests skip (NOT RUN) without fastapi. The merged suite (main into #353) is NOT RUN: this merge environment has no `pytest` and no `ruff`, so every count above is a pre-merge run of one side.
- Condition 2 and condition 3 were closed by the implementation this branch carries (`d-impl`), after this record was written; the pinned claims in this file were rewritten to match, but no post-implementation pytest run backs them.
- "unscoped" label: still nowhere in a card envelope or UI surface - the one strict xfail that remains.
- Condition 1 over HTTP (403 from `room_routes.py`) not exercised; Project Home 403 simulated by fixtures.
- Condition 4 keyboard and 390px: NOT RUN.
- Not checked: whether the run-2 day-alone test was scored before this started.

NEXT: Label the unscoped credential where a person reads it (a card envelope or UI surface, build-plan Q2) and flip the remaining strict xfail; run `python -m pytest -q tests/vnext tests/test_public_safety.py` on the merged tree; then run the `phone-390` e2e where a browser exists.
