# d-impl-review — independent review of the Stage D implementation (build-plan Steps 1–5)

**Read-only.** Nothing in this review changes code, tests or config; the only file this packet writes is
this one. Base reviewed: `3b49bc7` (d-plan) → `HEAD` (`22faa9c`,
`feat(worlds): Auth.scope, Action.state, …`). Working tree clean at `22faa9c`.

**Method.** `git diff 3b49bc7..HEAD`; read the plan (`build-plan.md` §4 Steps 1–5, §5, §6, §7), the contract
(`connect-contract.md` §4.2, §4.5, §6.1, §7.2), the author's record (`d-impl.md`) and every changed file.
Real `pytest` and `fastapi` are **not** in this sandbox; where I could, I executed the pure tests under a
stdlib pytest stand-in and wrote standalone probes (pydantic 2.12.5 + PyYAML present). Every run is labelled
here; nothing is claimed as "pytest passed".

## Verdict in one line
The three authorised behaviours are implemented, are fail-closed, and the four flipped pins are genuinely
earned; **no BLOCKER, no false-green pin**. The two real gaps are both about *proof and placement*, not a live
permissive defect.

## Findings, most severe first

### BLOCKER — none
Nothing in the diff leaves the authorised file set, and no flipped pin is a false green. Stated plainly, not
to pad: I looked for both and did not find them.

### MAJOR-1 — the backward-compatibility property is unguarded, and `d-impl.md` cites a test that does not test it
`d-impl.md:18–19` claims `action_version` "leaves each new field out of the hash at its default, so
authorizations requested before this change keep their version (`test_models.py:114`)." The cited test,
`tests/worlds/test_models.py:114–120`, does **not** assert that. Its three assertions are that a *non-default*
`state` / `scope` / `verified` **changes** the hash:
```
118  assert v != action_version(a.model_copy(update={"state": "proposed"}), r, p)
119  assert v != action_version(a, r, prov(auth=Auth(..., scope=["items"])))
120  assert v != action_version(a, req(method="POST", verified=True), p)
```
There is no comparison against the pre-change payload, so the test is silent on the property its name names.
I proved the gap: with the compatibility popping at `models.py:499–504` replaced by a naive hash that keeps all
new fields, the test **still passes** (probe `prove_weak.py`: "PASS (so it does NOT guard the property)").

Why it matters: the property is the mechanism that stops `config_store._refresh_versions` →
`dispatcher._on_actions_changed` (`dispatcher.py:314–322`) from invalidating live `pending`/`approved`
authorizations across an upgrade. The behaviour is **correct today** — I verified by hand that a default
`Action`/`Request`/`Auth` produces the same hash under the new code and the pre-change payload ("all defaults
new==old: True"; explicit-defaults == omitted-defaults: True) — but nothing in the committed suite would catch
its regression, while the record presents it as proven.

What I would change: keep the test, add a fixed expected-hash (or an explicit "new-default hash == hash of the
pre-change payload with the new keys removed") assertion so the property itself is pinned, and correct
`d-impl.md:19` to cite that assertion.

### MAJOR-2 — the scope *decision* runs inside the transport, which `connect-contract.md` §7.2 says it must not
The packet lists §7.2 as text "the code must now match". §7.2 (`connect-contract.md:555–558`) is explicit:
"`CredentialReference.scope` … is a *decision* before the send, so it belongs at the call sites that build a
request — `dispatcher._resolve` … — **not inside the transport**." The implementation puts the decision in the
transport: `scope_allows` is defined at `confinement.py:179–182` and evaluated from `_prepare` at
`confinement.py:601`. The transport now reads the credential scope and the request id to decide meaning.

Why it matters: §7.2's rationale is that "a transport that decided scope would have to know the capability
graph, which is meaning, and meaning is Worlds'". The code now does exactly that, so the contract sentence is
contradicted. Note the tension the plan already records: `build-plan.md:419–424` (Q1) lists this exact design
as option (a) and names option (b) — "the call site passes a pre-computed scope verdict into the transport,
which then refuses before `:593`" — as the alternative. The 2026-10-15 decision says the *check* runs "before
DNS in `confinement.py`", which option (b) also satisfies (the refusal is still in the transport, before DNS);
only the *decision* moves to the call site.

Why I am not calling this a live defect: the decision in force explicitly places the check in `confinement.py`
and "nothing else was authorised", and the security outcome is identical (proved below). But a code review
against the stated contract cannot record §7.2 as matched.

What I would change: either adopt plan option (b) — compute the verdict at `dispatcher._resolve`
(`dispatcher.py:189`) / the Connect call site and pass it in, so the transport only enforces — or get an owner
ruling that the decision in force supersedes §7.2, and record that in `d-impl.md`. Do not silently leave the
contract saying one thing and the code another.

### MINOR-1 — Step 3's second named pin (`:226`) is left strict, so Step 3 is only half-delivered
`build-plan.md:126–130` names **two** pins for Step 3: `:234` and `:226`
(`test_c3_unscoped_is_labelled_wherever_it_appears`). Only `:234` was flipped; `:226` remains
`xfail(strict=True)` at `tests/vnext/test_connect_proof.py:228–233`. `d-impl.md:30` and `:39–43` disclose this
honestly. The mitigating fact is in the plan itself: Q2 (`build-plan.md:425–428`) says the `unscoped` label is
undecided and "must be chosen … before Step 3 can satisfy `:226`", and the label would live in `cards.py`,
outside the authorised set. So leaving it strict is defensible and is the fail-safe direction — but Step 3's
status should read "one of two named pins" until the coordinator resolves the plan-vs-Q2 wording.
No change to the pin: relaxing or deleting it would be the wrong move.

### MINOR-2 — Step 2's planned "a scope entry naming no capability is refused rather than ignored" has no home
`build-plan.md:110–111` asks Step 2 to add a test that a scope entry matching no capability "is refused rather
than ignored" (`connect-contract.md:359`). The new `tests/worlds/test_models.py:99–104` covers `scope=None`,
`["health"]` and `[]` but not that case, and no validation anywhere rejects it. To be precise about the
fail-closed direction the brief asks about: this is **not** a permissive path in Steps 1–5. A typo'd scope entry
is simply never matched, so the capability it was meant to cover is *refused* (`scope_allows` returns False),
not allowed; e.g. `scope=["healtj"]` refuses a `…​.health` request. The contract's "refused rather than ignored"
is a save-time check that needs capability knowledge, which only the Step 6/8 register layer has.
What I would change: record this as an explicit Step 8 obligation in `d-impl.md` (or `build-plan.md`'s unknown
list) so it is not lost, rather than invent a model-level check that cannot know capabilities.

### MINOR-3 — `room0.candidates()` still reports "adopted" from file existence, ignoring the new `state`
`src/personal_world/worlds/room0.py:559` computes `"adopted": self._store.get("action", action_id) is not None`.
With `Action.state` now able to be `proposed`/`refused`/`expired`, an action that exists but is not adopted
would still be labelled `adopted: true` here, and `room0.adopted()` (`room0.py:563–577`) returns it without
checking state. This contradicts "no invented status". It is **latent, not reachable in Steps 1–5**: room0's own
`adopt()` writes state-less actions (default `adopted`, `room0.py:627–629`), and the only proposer (endpoint 9)
does not exist yet; any dispatch would still be refused by `dispatcher.py:223`. `room0.py` is not in Step 5's
file list.
What I would change: when Step 13 can write a `proposed` action, make both `candidates()` and `adopted()` read
`state == "adopted"`; track it now.

### MINOR-4 — two record strings are now stale
- `tests/vnext/test_connect_proof.py:3–4` still says "`Auth.scope` / `Action.state` are fields it PROPOSES",
  and `:6` says the file pins each contract-ahead-of-code place as a strict xfail. Two of those fields now
  exist and four of five pins are plain tests.
- The `:226` xfail reason at `test_connect_proof.py:228` — "no 'unscoped' label exists anywhere in src/ or
  ui/src" — is now false as written: the word appears in src at `confinement.py:180` and `models.py:113`
  (comments). The *assertion* (a card envelope label) still fails, so the strict xfail still behaves correctly.
What I would change: refresh both strings; they are documentation other reviewers will trust.

### MINOR-5 — the runtime half of the Step 5 test passes for a second reason, so `dispatcher.py:343` is uncovered
`test_c2_a_state_proposed_action_is_inert_at_dispatcher_and_runtime`
(`tests/vnext/test_connect_proof.py:365–382`) asserts `NotConsumable` at `:379–380`. That outcome is genuinely
produced, but not necessarily by the new check: rewriting the action to `proposed` changes
`action_version`, and `store.on_change` (`dispatcher.py:175`) → `_on_actions_changed` (`:314–322`) invalidates
the `approved` row, so `_consume` would raise `NotConsumable("authorization is invalidated")` at `:351` even with
`dispatcher.py:343–344` deleted. Line 343 is correct defence-in-depth, but no test uniquely exercises it.
The test *does* uniquely earn the dispatcher-visibility claim (`can_see`, `dispatcher.py:212`) and the
owner-refusal at `:223` — deleting `:223` makes the owner case pass and the test fail — so this pin is legitimately
flipped; only the `_consume` assertion is non-discriminating.
What I would change: add one case that reaches `_consume` with a *current-version* authorization for a
non-adopted action (or drop `:343` as provably redundant); either is fine, but say which.

### NIT-1 — `models.py:502` uses a tuple expression for its side effects
`request_d.pop("provenance"), request_d.pop("verified")` reads like a no-op tuple; it should be two statements.
Same for the pattern style at `:499–504`; harmless but easy to misread in a security-sensitive function.

### NIT-2 — two plan wordings have no committed proof (both vacuous, not wrong)
Step 5 asks the test to show a `proposed` action "is not acted on by the runner" (`build-plan.md:155–158`);
there is no runner assertion because `runner.py` never reads an `Action` at all — it imports only
`ConfinementError, ErrorClass, RawResponse` and sends `effect="read"` (`runner.py:268–271`), so `d-impl.md:22–23`
is confirmed and the runner half is vacuous. Step 1 mentions "an existing file that omits both still
round-trips through `ConfigStore`" (`build-plan.md:95–98`); the delivered `test_models.py` cases use
constructors, not the store. I verified the store path by hand (below), so this is a wording/coverage nit.

## The five pins, one by one
| Pin | Now | Earned? |
|---|---|---|
| `:220` | plain `test_connect_proof.py:221–225` | **Yes** — asserts `scope == ["health"]`, default `None`, and an invalid `Id` raising `ValidationError`; matches `models.py:114`. |
| `:226` | **still `xfail(strict=True)`** `:228–233` | Not flipped; disclosed (MINOR-1). Honest, not a false green. |
| `:234` | plain `:236–248` | **Yes** — asserts `auth_failed`, `lookups == []`, `dials.dialed == []`; I reproduced all three through `confined_request`. |
| `:341` | plain `:358–362` | **Yes** — `proposed` accepted, default `adopted`, `"executed"` refused; matches `models.py:476`. |
| `:347` | plain `:365–382` | **Yes** for visibility + owner refusal + no-dispatch; the `_consume` assertion is non-discriminating (MINOR-5). |

No pin was relaxed to non-strict, deleted, or marked passed without the behaviour behind it.

## The scope check really runs first (item 3) — traced and executed
Call order, from the code:
`confinement.confined_request` (`:546`) → `_send` (`:567`) → `_prepare` (`:579`) → the scope gate at
`confinement.py:601–603` → `resolve_within` at `confinement.py:605`. `build_url` (`:588`) only splits
scheme/host/port/target and does no resolution; the credential is attached later still, in `_exchange`
(`:643–644`). Every sender in the repo routes through `confined_request` (`companion.py:324`,
`connect_routes.py:66`, `dispatcher.py:165` default, `room0.py:289`, `server.py:140`), and the dispatcher's only
send is `dispatcher.py:385`, so the gate covers the C3 action path too.
Executed through the public entry point (probe `probe4.py`, recording resolver + stubbed dials):
```
scope=None      cap=other   -> confinement_denied  lookups=1 dials=0
scope=['health'] cap=other  -> auth_failed         lookups=0 dials=0
scope=['health'] cap=health -> confinement_denied  lookups=1 dials=0
scope=[]         cap=health -> auth_failed         lookups=0 dials=0
```
Out-of-scope and empty-scope are refused **before any name resolution**; in-scope still resolves; unscoped is
unchanged. Condition 3 is met.

## Backward compatibility (item 4) — loader and behaviour
The loader is `config_store._load_file` → `MODEL_BY_KIND[kind].model_validate` (`config_store.py:177`); missing
optional fields take their declared defaults. I loaded legacy on-disk `provider`/`request`/`action` YAML that
omits all four new keys (`probe5.py`): `errors: []`, `auth.scope is None`, `provenance="owner"`,
`verified=False`, `state="adopted"`. `save()` re-serialises the normalised model, so a re-save adds `scope: null`
to the file, but that is the store's pre-existing behaviour for every defaulted field and cannot change the
`test_config_store.py:101` content assertion (`"env:REF_TOKEN" in text`). The one behaviour that could have
silently changed — invalidation of existing authorizations via a moved hash — does **not**: default-valued
objects hash identically to the pre-change payload (proved above). `tests/worlds/test_config_store.py` is
untouched by the diff (`git diff --name-only`).

## Fail-closed direction (item 5)
- `scope=[]` → refused; a scope entry that matches nothing refuses the capability it should have covered, not
  permits it (MINOR-2). No permissive path found.
- `state` and `provenance` are closed `Literal`s (`models.py:476`, `:257`); out-of-set values raise
  `ValidationError` (tests `test_models.py:95–96`, `:110–111`). No out-of-set value is accepted.
- `confined_request` wraps `_send` in `try/except Exception → ConfinementError` (`:561–562`); `scope_allows`
  cannot raise (all `getattr` with defaults), and a malformed/absent request id yields capability `""`, which is
  refused unless an (impossible, `Id`-constrained) empty scope entry exists.
- `dispatcher.py:223` and `:343` refuse non-adopted actions for the owner too, and `_consume` is inside the same
  transaction that flips the row to `consumed` (`:335–361`), so there is no window between check and dispatch.

## Checks run here (all labelled)
- `git diff --name-status 3b49bc7..HEAD` → exactly 6 files: `models.py`, `confinement.py`, `dispatcher.py`,
  `test_connect_proof.py`, `test_models.py`, `d-impl.md`. No Memory store, art/canon, receipts, CI, contract,
  Connect endpoint or UI change. **Authority clean.**
- `python3 -I /tmp/d-review/run_pure.py` (stdlib pytest stand-in) → **passed**: all of `tests/worlds/test_models.py`
  (19 cases incl. the four new ones) and the six non-fixture proof tests (`:193`, `:211`, `:221`, `:236`, `:251`,
  `:358`). This is **not** real pytest.
- `python3 -I /tmp/d-review/probe.py` / `probe3.py` → defaults load with `scope=None`/`state=adopted`; default
  hashes equal the pre-change payload; non-defaults change them.
- `python3 -I /tmp/d-review/probe4.py` → scope-before-DNS table above.
- `python3 -I /tmp/d-review/probe5.py` → legacy on-disk files load clean; `action_version` computed.
- `python3 -I /tmp/d-review/prove_weak.py` → the cited version test passes with the compatibility code removed.

## NOT RUN
Real `pytest` (absent); the dispatcher/fastapi tests including `test_connect_proof.py:365` (`fastapi` absent —
under real pytest they SKIP, i.e. NOT RUN); `tests/worlds/test_config_store.py`; ruff; bandit; any browser/UI
check. I did not re-run the author's private stand-in script.

## Return
```
RESULT: done
CHANGED: docs/vnext/d-impl-review.md (new; nothing else touched)
CHECKS: git diff --name-status 3b49bc7..HEAD → 6 authorised files only; run_pure.py (stdlib pytest stand-in) → test_models.py 19/19 + 6 proof tests PASS; probe4.py → out-of-scope/empty scope auth_failed with 0 lookups, in-scope 1 lookup; probe3.py/probe5.py → legacy load defaults + default hash == pre-change; prove_weak.py → cited version test passes with compat code removed
EVIDENCE: confinement.py:179, :601, :605; dispatcher.py:212, :223, :343, :175, :314; models.py:114, :257, :258, :476, :499–504; test_connect_proof.py:221, :228, :236, :251, :358, :365, :379; test_models.py:99, :114–120; connect-contract.md:555–558; build-plan.md:110–111, :126–130, :419–428; d-impl.md:18–19, :30, :39–43; room0.py:559, :563, :627; config_store.py:177, :297
UNRESOLVED: NOT RUN — real pytest; dispatcher tests (test_connect_proof.py:365) and test_config_store.py (no pytest/fastapi in sandbox); ruff; bandit; UI/browser. Open for the coordinator: MAJOR-2 needs a ruling (plan option (b) vs owner decision) because a decision in force and contract §7.2 disagree.
NEXT: coordinator rules on MAJOR-2 (move the scope decision to the call site per §7.2, keeping the refusal before DNS in confinement.py) and has the author add the missing default-hash regression assertion for MAJOR-1 before merge.
```
