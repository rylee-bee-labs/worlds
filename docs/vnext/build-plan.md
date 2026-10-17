# Build plan — Worlds vnext / d-plan (PLAN ONLY)

> **Status: PLAN ONLY. Nothing here is built.** This is a sequence for a human to execute, written
> against a **MOCKUP** contract (`docs/vnext/connect-contract.md:3`) and two **DRAFT** proofs
> (`docs/vnext/proof/c-proof.md:3`, `docs/vnext/proof/c-room0.md:3`). PLAN ≠ PROTOTYPE ≠ APPROVED,
> and MOCKUP ≠ merged. No route in the contract's §3 exists, no field in its §2 is stored, and no
> security test in its §4 or §5 has been written (`connect-contract.md:1022`–`:1024`). Every step
> below is written in the tense that says so: **planned**, never done.
>
> **Date:** 2026-10-15 · **Task:** d-plan · **Reads with:** `docs/vnext/connect-contract.md` (#329),
> `docs/vnext/proof/c-proof.md`, `docs/vnext/proof/c-room0.md`, `docs/vnext/retire.md`.
>
> **Citations.** Every claim below cites `path:line` in this clone. Where a line is quoted the quote
> is from the file at that line. Contract sections are named as `§n` against
> `docs/vnext/connect-contract.md`.

## 0. How to read a step

Each step in §4 names five things, in this order:

1. **Contract** — the section it implements, as `§n` + `path:line`.
2. **Files** — the paths it touches (paths, not prose).
3. **Test (planned)** — the test that would prove it, and the *pinned* proof test it turns green.
4. **Protected** — `YES` (protected code: it is on Rylee's picker card in §5) or `no`.
5. **Depends on** — earlier steps. **Live effect** — whether running it would write, deploy or
   contact a live service (the Stage C card's "After the freeze", `c-room0.md:14`).

## 1. What this plan is, and is not

- It **is** the smallest honest order in which a human could turn the merged Connect contract and
  the Stage C proof into a working Worlds.
- It **is not** code, tests, CI or the contract. It changes nothing under `src/`, `tests/` or
  `.github/`, and it does not amend `connect-contract.md` (`c-room0.md:22`, `:24`).
- The contract's own status holds: it is a MOCKUP and it says so twice
  (`connect-contract.md:3`, `:1020`–`:1024`). A plan step that has not run is **planned**; a proof
  that used a stand-in runner is **DRAFT**; a merged document is **merged**, not tested, not
  deployed.

## 2. Decisions in force (quoted, not paraphrased)

- 2026-10-13 Rylee: "I'm wanting it to have a brand new design and new api connect layer." and
  "Not yet. Wanna get it cleaned up first then we design." / "Ok do add the api and visuals. Hah"
  — cleanup ran first and is merged (`docs/vnext/retire.md:136`); design and contract now exist as
  merged documents, not as running code.
- 2026-10-13 Rylee: "Queue all but offload the work you can so we can use it for benchmarks"
  (`c-room0.md:18`).
- 2026-10-14 23:30Z Rylee, Stage C card: "After the freeze" — Stage C stayed read-only, synthetic
  data only, never deployed, draft only (`c-proof.md:4`, `c-room0.md:14`). **Any step in this plan
  that would write, deploy or contact a live service is Rylee's to authorise, not mine to
  schedule quietly.**
- 2026-10-15 Claude, answering an `[architecture]` escalation: "Do not amend the contract: Rylee
  approved it with Sol's conditions 2 and 3 as gates (b-gate, 2026-10-13), so shrinking it to match
  the code would drop an owner gate. Keep the two proof tests xfail-strict, and put Auth.scope +
  Action.state (scope check before DNS in confinement.py) into the d-plan as protected-code work
  for Rylee's picker card; the plan only describes it, nothing is built." (`c-room0.md:22`–`:25`).
- Protected invariants that bind every step: local Memory; accessibility floors; zero-provider
  usability; security/consent; no invented status; "external systems keep their own authority
  (Project Home owns operational authority, Companion owns chat, services own data)"
  (`c-room0.md:29`–`:31`).
- Status words stay honest: MOCKUP ≠ PROTOTYPE ≠ APPROVED; merged ≠ tested ≠ deployed; a plan step
  that has not run is written as planned, never as done.

## 3. Ordering, and why this order

The first four steps are the ones that unblock the most, cheapest:

1. They are the four additive *optional* model fields the contract's §6.1 says are the **only**
   thing v1 adds (`connect-contract.md:447`–`:452`). Two of them (`Auth.scope`, `Action.state`) are
   the protected-code gate; the other two (`Request.provenance`, `Request.verified`) are not, so
   they can land without waiting on the card.
2. They turn **five currently-strict `xfail`s green** — the honest gate the proofs left behind
   (`tests/vnext/test_connect_proof.py:220`, `:226`, `:234`, `:341`, `:347`). Nothing else in the
   plan can be honestly called "done" while those pins still fail.
3. Only then do the typed models (§2) and the endpoints (§3) get built on top. Endpoints that sit
   on unbuilt fields would be endpoint-shaped *mockups*, not endpoints.

## 4. The steps

### Step 0 — Rylee answers the protected-code card (a decision, not code)

- **Contract** — §4.2 (`connect-contract.md:287`), §4.5 (`:322`), §6.1 (`:449`, `:452`). The card is
  §5 below.
- **Files** — none.
- **Test (planned)** — none. This step *is* the gate the five strict `xfail`s
  (`tests/vnext/test_connect_proof.py:220`, `:226`, `:234`, `:341`, `:347`) wait behind.
- **Protected** — YES. It is the protected-code decision itself.
- **Depends on** — nothing. **Live effect** — none.
- Steps 3, 4, 5, 6 below cannot start until this is answered. Steps 1, 2, 7+ can.

### Step 1 — Add the two non-protected additive model fields

- **Contract** — §6.1 `Request.provenance` (`connect-contract.md:450`) and `Request.verified`
  (`:451`); consumed by §4.8 (`:362`–`:364`).
- **Files** — `src/personal_world/worlds/models.py` (edit `Request`, `models.py:240`–`:305`).
- **Test (planned)** — `tests/worlds/test_models.py`: `Request` defaults to
  `provenance="owner"`, `verified=False`; an existing file that omits both still round-trips
  through `ConfigStore` unchanged. Also `tests/worlds/test_config_store.py` must stay green
  unchanged (the contract's "every existing file stays valid", `connect-contract.md:475`).
- **Protected** — no.
- **Depends on** — nothing. **Live effect** — none (a model field; no route).

### Step 2 — Add `Auth.scope`

- **Contract** — §4.2 `CredentialReference.scope` (`connect-contract.md:287`), §6.1
  `Auth.scope: list[Id] | None` default `None` (`:449`).
- **Files** — `src/personal_world/worlds/models.py` (edit `Auth`, `models.py:78`–`:159`; `extra`
  at `:101`).
- **Test (planned)** — **flips** `tests/vnext/test_connect_proof.py:220`
  (`test_c3_auth_scope_exists_and_none_is_the_legacy_unscoped_state`) from strict `xfail` to a
  plain test. Add `tests/worlds/test_models.py` cases: `scope=None` is today's unscoped provider;
  a scope entry that matches no capability is refused rather than ignored (`connect-contract.md:359`).
- **Protected** — **YES** — picker card item **A** (§5).
- **Depends on** — Step 0. **Live effect** — none.

### Step 3 — Enforce scope before any DNS lookup

- **Contract** — §4.2 "A capability outside `scope` is `auth_failed` before any socket opens — no
  DNS, no bytes" (`connect-contract.md:287`); §5.1 (`:383`); §7.2 places the *decision* at the call
  sites, not in the transport (`:555`–`:558`).
- **Files** — the check must run before `confinement._prepare` reaches
  `confinement.py:593` (`resolve_within`), and the credential is only applied later, in `_send`'s
  `_auth_headers` call (`confinement.py:565`). Candidate edit sites are
  `src/personal_world/worlds/confinement.py` and/or the new Connect call path
  (`src/personal_world/worlds/dispatcher.py:189` `_resolve`). **Placement is an open question — see
  §7, Q1.** This plan does not choose between the options.
- **Test (planned)** — **flips** `tests/vnext/test_connect_proof.py:234`
  (`test_c3_out_of_scope_capability_fails_before_any_dns_lookup`) and `:226`
  (`test_c3_unscoped_is_labelled_wherever_it_appears`) from strict `xfail` to plain tests: an
  out-of-scope capability fails `auth_failed` with `lookups == []`; an unscoped credential is
  labelled `unscoped` wherever it appears.
- **Protected** — **YES** — picker card item **C** (§5).
- **Depends on** — Steps 0, 2. **Live effect** — none in the test (the proof stubs the dial
  functions, `test_connect_proof.py:176`–`:190`); it does **not** open a socket.

### Step 4 — Add `Action.state`

- **Contract** — §4.5 `state` (`connect-contract.md:322`), §6.1 `Action.state` default `"adopted"`
  (`:452`).
- **Files** — `src/personal_world/worlds/models.py` (edit `Action`, `models.py:460`–`:476`).
- **Test (planned)** — **flips** `tests/vnext/test_connect_proof.py:341`
  (`test_c2_a_state_proposed_action_can_exist`) from strict `xfail` to a plain test; an `Action`
  file that omits `state` reads as `adopted`, so every existing action behaves exactly as today
  (`connect-contract.md:452`).
- **Protected** — **YES** — picker card item **B** (§5).
- **Depends on** — Step 0. **Live effect** — none.

### Step 5 — Make a `proposed` action inert at dispatch and at runtime

- **Contract** — §4.5 "`adopt` sends nothing; `execute` needs a consumed authorization"
  (`connect-contract.md:322`); §6.1 "A `proposed` action is already inert: `exposed: false`, and a
  write still needs a consumed authorization to dispatch" (`:452`).
- **Files** — `src/personal_world/worlds/dispatcher.py` (the action-visibility and dispatch path,
  `dispatcher.py:210` `can_see`, `:217` `request_authorization`, `:259` `approve`); `runner.py` if
  the runtime half needs it.
- **Test (planned)** — **flips** `tests/vnext/test_connect_proof.py:347`
  (`test_c2_a_state_proposed_action_is_inert_at_dispatcher_and_runtime`) from strict `xfail` to a
  plain test asserting a `proposed` action is refused by the dispatcher and is not acted on by the
  runner.
- **Protected** — **YES** — the dispatcher is the at-most-once action machinery named as protected
  in `retire.md:69`; picker card item **B** (§5).
- **Depends on** — Steps 0, 4. **Live effect** — none.

### Step 6 — The typed Connect models

- **Contract** — §2, "the implementation would be Pydantic models beside
  `src/personal_world/worlds/models.py`" (`connect-contract.md:72`–`:73`, types `:75`–`:231`); the
  persistence projection in §6.1 (`:430`–`:464`). Also §7.3's authority adapt
  (`:586`–`:588`) and §6's `dialect`-vs-`kind` rule (`:476`–`:477`).
- **Files** — new `src/personal_world/worlds/connect_models.py` (descriptor, capability, read spec,
  credential reference, test result, card draft, publish selection, action proposal, disconnect /
  revocation results); `src/personal_world/worlds/models.py` only if a field must project onto C1
  (`Provider.principal_id`, `models.py:180`; `Card.meaning`, `models.py:321`).
- **Test (planned)** — new `tests/vnext/test_connect_models.py`: every §2 refusal — `extra="forbid"`
  on each model; closed enums (`dialect`, `auth`, `authority`, `state`, `SourceState`,
  `Freshness`); `card_id` is a single `ID_RE` segment (`models.py:11`); `request_id` is exactly two
  `REQUEST_ID_RE` segments (`models.py:14`); `principal` with any part other than `person_ref`
  refused (`connect-contract.md:274`). The models it embeds are the Step 2 / Step 4 fields.
- **Protected** — no directly; it *embeds* the two protected fields, so it inherits their gate.
- **Depends on** — Steps 1, 2, 4. **Live effect** — none.

### Step 7 — `discover` endpoint

- **Contract** — §3 endpoint 1 (`connect-contract.md:240`); worked integration A step 1 (`:642`–`:666`).
- **Files** — `src/personal_world/worlds/connect_routes.py` (or a new
  `src/personal_world/worlds/connect_v1.py`); the document-bounding discipline to move in is
  `src/personal_world/worlds/recipes.py:165`–`:217` (bounds at `:163`–`:170`; `needs_auth: unknown`
  at `:328`).
- **Test (planned)** — new `tests/vnext/test_connect_endpoints.py`: a 3 MB / 10 000-node document is
  refused with a plain message; only GET/HEAD survive; `servers[]` is ignored in favour of the
  synthetic placeholder; an unmapped auth scheme reads `needs_auth: unknown`.
- **Protected** — no. **Depends on** — Step 6. **Live effect** — one bounded read when an owner runs
  it: **a live-service contact, Rylee's to authorise after the freeze**.

### Step 8 — `register` endpoint

- **Contract** — §3 endpoint 2 (`connect-contract.md:241`); §6.1 persisted table (`:432`–`:439`);
  §7.1's "Connect must not add" list (`:526`–`:531`).
- **Files** — `src/personal_world/worlds/connect_routes.py`; through the existing
  `src/personal_world/worlds/config_store.py` (`_check_id` `:119`, etag preconditions `:276`,
  reference checks `:326`).
- **Test (planned)** — new tests asserting: an id is validated before a path is built; the
  placeholder `base_url` is refused (`recipes.py:589`); `If-None-Match: *` creates and a real etag
  updates; a credential value anywhere in the body is refused by `extra="forbid"`
  (`models.py:101`); a capability with no `ReadSpec` is refused (`connect-contract.md:362`).
- **Protected** — no. **Depends on** — Steps 6, 7. **Live effect** — **writes C1 config**
  (owner-only, CSRF, `connect-contract.md:235`). Rylee's to authorise; not scheduled quietly.

### Step 9 — The three read endpoints

- **Contract** — §3 endpoints 3–5 (`connect-contract.md:242`–`:244`); consumers named there
  (Connect list/detail, `/api/boards/home`).
- **Files** — `src/personal_world/worlds/connect_routes.py` (or `connect_v1.py`).
- **Test (planned)** — new tests: owner-only; `Cache-Control: no-store`; the descriptor cannot leak
  more than the config already holds; no capability is callable from a description.
- **Protected** — no. **Depends on** — Step 8. **Live effect** — none (reads).

### Step 10 — `test` endpoint

- **Contract** — §3 endpoint 6 (`connect-contract.md:245`); §4.3 (`:292`–`:302`); §7.2 (the
  confinement seam is the only outbound path, `:533`–`:554`).
- **Files** — `src/personal_world/worlds/connect_routes.py`; through
  `src/personal_world/worlds/confinement.py` (`_prepare` `:571`, DNS `:593`, read-cannot-mutate
  `:577`); supersedes the live `/api/connect/try` (`connect_routes.py:119`).
- **Test (planned)** — new tests: a write is refused 422 as `connect_routes.py:115` does; rate limit
  10/min (`connect_routes.py:34`); a response body echoing the live token has the token replaced
  (`connect_routes.py:191`); `PW_*`/`OIDC_*`/`BOOTSTRAP` refs refused (`connect_routes.py:37`);
  an out-of-scope capability never reaches DNS (Step 3's pin).
- **Protected** — no (it consumes the Step 3 seam). **Depends on** — Steps 8, 3. **Live effect** —
  one bounded read per call: **a live-service contact, Rylee's to authorise**.

### Step 11 — `transform` endpoint

- **Contract** — §3 endpoint 7 (`connect-contract.md:246`); §4.7 (`:337`–`:350`).
- **Files** — `src/personal_world/worlds/connect_routes.py`; JSONPath subset checked by
  `models.py:26` (`_check_path`).
- **Test (planned)** — new tests: pure (no network, no persistence); every draft key exists in the
  `TestResult.values` it was built from; no key from a `truncated` sample; a draft built from a
  `stale` result publishes only as `stale`.
- **Protected** — no. **Depends on** — Step 10. **Live effect** — none.

### Step 12 — `publish` endpoint (selective) + the room0 adapt

- **Contract** — §3 endpoint 8 (`connect-contract.md:247`); §4.4 (`:304`–`:311`); §7.3's two adapts —
  *selective publish* (`:580`–`:584`) and the explicit `authority` field (`:586`–`:588`).
- **Files** — `src/personal_world/worlds/connect_routes.py`; `src/personal_world/worlds/room0.py`
  (`home_items` lands every card today, `room0.py:493`; the authority read is
  `models.py:203`–`:204`); through `config_store.py` (`:326`, `:358`).
- **Test (planned)** — new tests: `published` is an allow-list, never a wildcard; a hidden
  capability appears in no `/api/boards/home` payload; an agent token is refused; publish only of a
  `CardDraft` the owner already saw from a `test`; hidden capability named only in the receipt and
  Connect detail (`connect-contract.md:309`).
- **Protected** — no. **Depends on** — Step 11. **Live effect** — **writes a card + board item.**
  Rylee's to authorise.

### Step 13 — `propose-action` and `adopt`

- **Contract** — §3 endpoints 9–10 (`connect-contract.md:248`–`:249`); §4.5 (`:313`–`:322`);
  §5.2 (`:408`).
- **Files** — `src/personal_world/worlds/connect_routes.py`; `dispatcher.py` for the
  authorization split (`:217`, `:259`), which already exists and is not moved.
- **Test (planned)** — new tests: `exposed: false` not settable here; `approval: never` on a write
  refused unless the owner's waiver is in config (`config_store.py:355`); `idempotency: required`
  for an external write; `adopt` sends nothing (`room0.py:604`) and an id a provider could not have
  minted is refused 400 (`room0.py:546`).
- **Protected** — no directly; it depends on the Step 4/5 protected field and enforcement.
- **Depends on** — Steps 4, 5, 8. **Live effect** — none (propose and adopt send nothing).

### Step 14 — `disconnect` and `revoke`

- **Contract** — §3 endpoints 13–14 (`connect-contract.md:252`–`:253`); §4.6 (`:324`–`:333`).
- **Files** — `src/personal_world/worlds/connect_routes.py`; `config_store.py` (deletes refused
  while referenced, `:358`); `confinement.py` (`_session_forget` `:298`, the only credential purge
  in code, and it drops a held token, not a `room0` bearer reference — see §7, Q3).
- **Test (planned)** — new tests: disconnect refused while an authorization is pending unless the
  owner names it; after revoke, a second call resolves no credential and sends nothing; the report
  says `external_state_untouched: true` and tells the owner to revoke at the provider.
- **Protected** — no. **Depends on** — Steps 8, 12, 13. **Live effect** — **deletes config
  objects.** Rylee's to authorise.

### Step 15 — Replace the recipe install path; decide the 16 directories

- **Contract** — §7.4 (`connect-contract.md:607`–`:633`); §3 endpoint 2 carries the job
  (`:629`).
- **Files** — `src/personal_world/worlds/recipes.py` (`install()` has no caller anywhere in `src/`,
  `:615`); `config/recipes/` (16 directories, `:614`); `src/personal_world/framework.py`
  (the loader's validating half is a real consumer, `framework.py:198`).
- **Test (planned)** — `tests/recipes/` and `tests/worlds/test_room_recipes.py` move with the code
  they cover; the framework validator stays green.
- **Protected** — no. **Depends on** — Steps 7, 8. **Live effect** — none; the *fate of the 16
  directories* is a separate owner decision (`connect-contract.md:948`), not taken here.

### Step 16 — Connect UI, selective publish, and the accessibility pass

- **Contract** — §3's named consumers (`connect-contract.md:240`, `:247`); §6's row for
  `/api/connect/try` and `/preview` (`:478`).
- **Files** — `ui/src/fd/Connect.tsx` (recipe stub today, `Connect.tsx:711`), `ui/src/fd/api.ts`
  (`tryConnect`, `api.ts:180`), `ui/src/fd/Home.tsx`; Playwright specs under `ui/e2e-fd/`.
- **Test (planned)** — `ui/e2e-fd/connect-memory.spec.ts` plus a `phone-390` project run and a human
  screen-reader pass.
- **Protected** — no. **Depends on** — Steps 7–15. **Live effect** — the `/try` and `/preview` paths
  are kept until the UI moves in one step (`connect-contract.md:478`); moving them is Rylee's call
  (`:943`).

### Step 17 — Decide how endpoint 12 verifies a Project Home approval (open question, not a step)

- **Contract** — §7.3 known gap (`connect-contract.md:590`–`:605`); §10 (`:945`–`:946`); §3
  endpoint 12 (`:251`).
- **Files** — `src/personal_world/worlds/dispatcher.py` (`record_project_home_approval` refuses on
  its first statement, `:277`–`:278`); today production supplies **no** verifier
  (`production.py:95`), so the path fails closed and the answer route is 403
  (`room_routes.py:75`–`:76`).
- **Test (planned)** — the three `test_c1_*` tests already pass at the dispatcher
  (`c-proof.md:72`–`:79`); the HTTP 403 on the wire is **NOT RUN** (`c-proof.md:77`).
- **Protected** — YES (the dispatcher). **Depends on** — Step 0 and a design decision this plan
  cannot make. **Live effect** — none until decided. Recorded as an open question in §7, Q4.

## 5. The protected-code card for Rylee

This is a **description of a decision**, not a request for it, and not work this task does. The
three items are exactly the set the 2026-10-15 decision names (`c-room0.md:24`–`:25`). Each has a
picker answer: **yes** (build it under this plan) or **no** (the contract's promise stays
unimplemented and the proof's pins stay red).

### A. `Auth.scope: list[Id] | None`, default `None`

- **What it unblocks** — §4.2's scoped access (`connect-contract.md:287`) and §6.1's
  `Auth.scope` (`:449`). Endpoint 2 then writes an explicit scope on every Connect-created
  connection, and the fail-closed check in §4.2 applies to all of them. Turns
  `tests/vnext/test_connect_proof.py:220` green.
- **What breaks if refused** — a credential is for the **whole provider**. Today's code says so
  plainly: `"scope" not in Auth.model_fields` (`test_connect_proof.py:199`) and the legacy
  behaviour is pinned by `test_c3_today_a_credential_applies_to_every_request_of_the_provider`
  (`:193`). §4.2's row and §5.1's threat row (`:383`) stay false in code, and Connect cannot write a
  scoped connection at all.
- **What "no" means** — keep unscoped credentials as the only state; scope stays a contract-only
  promise; `connect/v1` either refuses every scoped credential or silently drops the scope — either
  way §323's "every field ... has a named consumer, a reason to exist and a security test"
  (`connect-contract.md:20`) is not met for this field.

### B. `Action.state: "proposed" | "adopted" | "refused" | "expired"`, default `"adopted"`

- **What it unblocks** — §4.5's `state` (`connect-contract.md:322`) and §6.1's `Action.state`
  (`:452`). A proposal can exist between endpoint 9 (propose) and endpoint 10 (adopt). Turns
  `tests/vnext/test_connect_proof.py:341` and, with enforcement, `:347` green.
- **What breaks if refused** — no `Action` can be `proposed`:
  `test_c2_a_state_proposed_action_can_exist` fails with `ValidationError` today
  (`test_connect_proof.py:343`–`:344`; `c-room0.md:245`–`:249`). Endpoint 9's whole purpose — record
  a proposal and stop (`connect-contract.md:64`) — has nowhere to record it.
- **What "no" means** — proposals cannot exist as state; an adopt step has nothing to read between
  endpoints 9 and 10; the only inertness stays `exposed: false` (`dispatcher.py:210`), which the
  proof already calls "a proxy, not the condition" (`c-proof.md:88`–`:89`).

### C. The scope check runs before DNS resolution in `confinement.py`

- **What it unblocks** — §4.2's "`auth_failed` before any socket opens — no DNS, no bytes"
  (`connect-contract.md:287`) and §5.1's threat row (`:383`). Turns
  `tests/vnext/test_connect_proof.py:234` green. Today `_prepare` resolves DNS at
  `confinement.py:593` and the credential is only applied afterwards, in `_send`'s `_auth_headers`
  call at `confinement.py:565`; the observed result is that a bearer credential for `/other` reached
  DNS (`lookups= 1`, `dials= 0`, `c-proof.md:94`–`:97`).
- **What breaks if refused** — an out-of-scope capability is not refused before DNS. The three
  strict pins (`test_connect_proof.py:220`, `:226`, `:234`) stay red, and condition 3 of Sol's
  gates cannot pass (`c-room0.md:22`–`:25`).
- **What "no" means** — accept that a credential can be sent to a capability outside its intended
  scope once the provider is registered; §4.2 and §5.1's rows are then statements about an
  intention, not about the code. Note the contract also says *where* the decision belongs
  (§7.2, `:555`–`:558`), which is a placement question, not a yes/no one — see §7, Q1.

## 6. What the proof already establishes, and what it does not

**Establishes** (read-only, synthetic, no network, no real credential; run with the authors' own
stand-in runner, not real pytest — `c-proof.md:16`–`:22`, `c-room0.md:47`–`:56`):

- The journey empty → connected → card → stale → unknown → recovery → disconnect → still usable,
  with the secret **value** never on disk or in any envelope (`c-proof.md:54`–`:63`;
  `test_connect_proof.py:81`–`:150`).
- Read-only end to end: every sender call in the journey was `effect="read"`, `GET`; a `POST` behind
  a card is `confinement_denied` with zero sender calls (`c-proof.md:102`–`:107`).
- Project Home/`project_home`-governed operations fail closed at the dispatcher: with no verifier, a
  refusing verifier, or a verifier that raises, the authorization stays `pending`, `execute` raises
  `NotConsumable`, the sender is never called (`c-proof.md:70`–`:79`; `c-room0.md:194`–`:221`).
- room/0 across the three states the card names — zero-provider is empty and honest; a stale card is
  never current; a revoked room (its own 401/403) is named `auth_failed`, stale, and not retried
  (`c-room0.md:96`–`:192`).

**Does not establish** — and this plan does not pretend otherwise:

- **Real pytest and real fastapi never ran** (`c-proof.md:28`–`:30`, `:123`; verified again in this
  clone: `python3 -m pytest` → `No module named pytest`). The dispatcher tests were run under a
  `fastapi` stub; under real pytest without the extra they `SKIP`, i.e. **NOT RUN**
  (`test_connect_proof.py:252`).
- **Condition 2 is not met.** `Action` has no `state` (`models.py:460`–`:476`), so no action can be
  `proposed`. Carried forward as `xfail(strict=True)` at `tests/vnext/test_connect_proof.py:341`
  and `:347`. **Step 4** turns `:341` green; **Step 5** turns `:347` green.
- **Condition 3 is not met.** `Auth` has no `scope` (`models.py:101`, `extra="forbid"`) and
  `confinement.py` contains no scope check; DNS resolves at `confinement.py:593` before any
  credential decision. Carried forward as `xfail(strict=True)` at
  `tests/vnext/test_connect_proof.py:220`, `:226`, `:234`. **Step 2** turns `:220` green; **Step 3**
  turns `:226` and `:234` green.
- **The HTTP layer is not exercised.** `room_routes.py:75`–`:76` maps `NotPermitted` to 403, but the
  proof shows the refusal at the dispatcher, not on the wire (`c-proof.md:77`–`:79`); a real Project
  Home 403 is only simulated by fixtures.
- **The browser half of condition 4 is NOT RUN.** No node, no `ui/node_modules`, no browser in the
  proof sandbox (`c-proof.md:108`–`:110`). Keyboard visibility of stale/unknown/retry and the 390px
  layout are **NOT RUN**. A human screen-reader and physical-device pass is **NOT RUN until a human
  runs it** (`c-room0.md:287`).
- **No room0 surface names a revocation as such.** There is no room0 revoke/disconnect route and no
  `revoked` state; removing the provider makes the room vanish rather than say "revoked"
  (`c-room0.md:187`–`:192`). The contract's endpoints 13–14 are MOCKUP.

**Note the pins are strict.** If any of the five turns green while the plan says it is still red —
or vice versa — the file fails. That is deliberate: it makes "not built" and "built" distinguishable
(`c-room0.md:234`–`:236`).

## 7. Explicit unknowns

Listed as UNKNOWN with the evidence gap. Never estimated, never quietly assumed.

- **Q1 — Where does the scope check live?** §7.2 says the *decision* belongs at the call sites
  (`connect-contract.md:555`–`:558`), while the 2026-10-15 decision says the check runs "before DNS
  in `confinement.py`" (`c-room0.md:24`). Options: (a) `_prepare` compares the request's capability
  against `Auth.scope` before calling `resolve_within` at `confinement.py:593`; (b) the call site
  passes a pre-computed scope verdict into the transport, which then refuses before `:593`. Not
  decided here.
- **Q2 — What does "unscoped" look like, and where is it labelled?** The word `unscoped` occurs in
  no file under `src/` or `ui/src` (`c-proof.md:92`–`:98`); pin at
  `tests/vnext/test_connect_proof.py:226`. A label must be chosen (descriptor field? card copy?)
  before Step 3 can satisfy `:226`. Not decided here.
- **Q3 — What is a "revoked connection" for a `room0` provider?** The only credential purge in code
  is `confinement._session_forget` (`confinement.py:298`), which drops a held cookie/token, not a
  `room0` bearer reference (`c-room0.md:187`–`:192`). Contract §4.6's `RevocationResult` is MOCKUP.
- **Q4 — How does endpoint 12 verify a Project Home approval?** No verifier is wired; production
  supplies none (`production.py:95`), so `record_project_home_approval` raises on its first
  statement (`dispatcher.py:277`–`:278`) and the path is 403. The contract explicitly does not
  invent one (`connect-contract.md:945`–`:946`). Not decided here.
- **Q5 — `SourceState` names `stale`; the code expresses stale as `freshness: "stale"` with
  `source_state: "unavailable"`** (`c-proof.md:67`–`:68`; `room0.py:421`). "A naming difference to
  settle, not a failure" (`c-proof.md:68`). Not settled here.
- **Q6 — The `dialect` ↔ `kind` projection.** The contract's `dialect` is `http-json | openapi-3 |
  room-0` (`connect-contract.md:79`); the code's `Provider.kind` is `http | room0 | reference`
  (`models.py:170`), and §6 says no third `kind` may be added (`:477`). No mapping function exists
  yet; Step 6 must state one, and the contract does not.
- **Q7 — The brief names `docs/vnext/ledger.md`; no such file exists at this base.** Verified:
  `find . -iname '*ledger*'` returns only `design/concepts/assets/packets/p1-ledger.jpg` and
  `docs/vnext/prototype/art/empty-ledger.webp`, and `git log --all -- docs/vnext/ledger.md` is
  empty. The Stage 0 keep-or-retire ledger is `docs/vnext/retire.md:1`. The UNKNOWN registers that
  do exist are `docs/vnext/docs-truth.md:93` (runtime revision; OpenAPI/route-inventory drift) and
  `docs/vnext/inventory.md:249` (vault wiring; provider adapters; workbench ADR-0003; generated-tree
  wiring; `cli_dispatch.py`; room/0 semantics). This plan carries those forward rather than
  re-deriving them.
- **Q8 — `vault:` refs resolve to `None` in production today**; `worlds/secrets.py:21` `set_vault`
  has no production caller (`inventory.md:251`). Whether the front door adopts the vault is open.
- **Q9 — The original contract review is absent.** `docs/vnext/connect-contract-review.md` is not in
  this clone and not on any reachable ref, so six findings (four MINOR, two NIT) were never matched
  one-to-one (`connect-contract.md:957`–`:963`, `:991`–`:995`, `:1006`). The coordinator holds the
  match.
- **Q10 — Whether the run-2 day-alone test was scored** before Stage C started is not checkable
  from the clone (`c-proof.md:6`, `c-room0.md:288`).
- **Q11 — Contract promises the proof could not exercise:** registration/discovery end to end (no
  endpoint exists), `PublishSelection.hidden`, `status_map` translation, the `meter` field's
  omission rule, `truncated` → no-published-field, the `principal` object→string projection, the
  `rotated_at` echo, and a card field that renders a link (the proof proves only `room0.valid_link`,
  `c-proof.md:66`–`:68`).

## 8. Not in this plan

Work that stays out, each with its reason.

- **`Auth.scope` and `Action.state` implementation, and the scope-before-DNS check** — described in
  §4/§5, gated on Rylee's picker card, and **not built by this task** (`c-room0.md:24`–`:25`).
- **Amending the contract** — refused. Rylee approved it with Sol's conditions 2 and 3 as gates
  (b-gate, 2026-10-13); shrinking it to match the code would drop an owner gate (`c-room0.md:22`).
- **Any write, deploy or live-service contact** — Stage C stayed read-only, synthetic, never
  deployed, draft only ("After the freeze", `c-proof.md:4`); such steps are Rylee's to authorise.
- **Old recipe-UI wiring (#320)** — stays parked; the contract says so and does not un-park it
  (`connect-contract.md:631`; `contracts-audit.md:103`).
- **The semantic-kernel refactor (#267)** — out of bounds; the contracts audit holds its work
  behind "#267 Packet A inventory and ADR-0009 owner review" (`contracts-audit.md:15`, `:325`,
  `:344`), and `ui/src/generated/*` still has no `ui/src/fd` consumer (`inventory.md:132`).
- **A new backend** — ruled out by #321 and §7: a replacement would have to re-prove SSRF refusal,
  credential non-disclosure and the single-attempt rule for no gain in fit
  (`connect-contract.md:560`–`:562`).
- **Moving `/api/connect/try` and `/preview` for tidiness** — they are kept until the UI moves in
  one step (`connect-contract.md:478`, `:943`).
- **A results table or any data migration** — refused by §6.2 (`connect-contract.md:488`–`:497`);
  `TestResult` is deliberately not persisted (`:459`).
- **Retiring `retire.md`'s kept units** — protected code, contract vocabulary and decision-bound
  surfaces are named, not removed (`retire.md:59`–`:90`).
- **Retiring the 16 recipe directories or `cli_dispatch.py`** — the directories' fate is a separate
  owner decision (`connect-contract.md:948`); `cli_dispatch.py` stays under #321's preservation rule
  (`retire.md:75`, `:140`).
- **Any UI design decision** — "A brand new design" is Rylee's call and not the contract's
  (`connect-contract.md:947`).

## 9. Test strategy (one section)

- **The gate for each step is a named test**, and for the five security pins it is
  `xfail(strict=True)` in `tests/vnext/test_connect_proof.py`. A step has not landed while its pin
  is still `xfail`; a pin that turns green without its step fails the suite loudly
  (`c-room0.md:234`–`:236`).
- **What runs in CI.** `validate.yml`'s `test` job runs pytest over `tests/` (`testpaths = ["tests"]`,
  `pyproject.toml:42`) with `--timeout=30`, plus ruff and bandit
  (`.github/workflows/validate.yml:38`–`:41`). `tests/vnext` is inside `tests/`, so the Stage C and
  room/0 proofs run there — and because `fastapi` is a runtime dependency (`pyproject.toml:10`) and
  CI installs `--extra test --extra crypto` (`validate.yml:40`), the dispatcher tests that
  `importorskip("fastapi")` (`test_connect_proof.py:252`) **run for real in CI**, not skipped.
  `tests/test_docs.py` gates internal markdown links and anchors, so this plan's links must resolve.
- **What runs on a browser.** `validate.yml`'s `browser` job runs `npx playwright test` in `ui/`
  (`.github/workflows/validate.yml:60`–`:67`); `ci.yml` runs the UI unit/lint/build job
  (`.github/workflows/ci.yml:1`). The `phone-390` project and `ui/e2e-fd/connect-memory.spec.ts` are
  the browser gate for Step 16.
- **Where a human is still required.** Keyboard-only visibility of the stale/unknown/retry states,
  the 390px layout, a screen-reader pass and a physical-device pass are **NOT RUN** in any proof so
  far (`c-proof.md:108`–`:110`, `c-room0.md:285`–`:287`) and cannot be green until a human runs them.
  `uat-live.yml` is manual-only against a live instance (`.github/workflows/uat-live.yml:22`).
- **The claims gate.** A step's PR body must carry the command that produced each strong claim and
  the observed output (`.github/workflows/ci.yml:35`–`:47`); a claim with no command fails.

## 10. Verification actually run for this document

Only what was run is recorded. This change adds documentation; it does not run the project's tests
because no test covers a plan.

| # | Command | Observed |
|---|---|---|
| A | `find . -iname '*ledger*' -not -path './.git/*'` | two image assets only (`p1-ledger.jpg`, `empty-ledger.webp`); no `docs/vnext/ledger.md` |
| B | `git log --all --oneline -- docs/vnext/ledger.md` | empty |
| C | `python3 -V; python3 -c "import pytest"` | `Python 3.14.7`; `ModuleNotFoundError: No module named 'pytest'` |
| D | `python3 -c "import fastapi"` | `ModuleNotFoundError: No module named 'fastapi'` |
| E | `python3 -c "import yaml; import pydantic"` | yaml + pydantic import OK |
| F | `test -s docs/vnext/build-plan.md && grep -c "path:line\|:[0-9]" docs/vnext/build-plan.md` | `198`, exit 0 |
| G | `python3 -m compileall -q src tests` | exit 0, no output |
| H | stdlib re-implementation of `tests/test_docs.py`'s link/anchor rule over the two new files (script kept outside the repo at `/tmp/doclink/check.py`) | both files `links_ok anchors_ok`, exit 0 |

## Return

```
RESULT: done
CHANGED: docs/vnext/build-plan.md (new), docs/vnext/README.md (new, short index)
CHECKS: A-E above in §10; F acceptance `test -s docs/vnext/build-plan.md && grep -c "path:line\|:[0-9]" docs/vnext/build-plan.md` → 198, exit 0; G `python3 -m compileall -q src tests` → exit 0; H stdlib docs link/anchor check over the two new files → links_ok anchors_ok, exit 0
EVIDENCE: path:line citations throughout §4-§9; pins at tests/vnext/test_connect_proof.py:220, :226, :234, :341, :347; gaps at src/personal_world/worlds/models.py:460-476 and confinement.py:571-593
UNRESOLVED: Q1-Q11 in §7 (scope-check placement; "unscoped" label; room0 revocation; endpoint-12 verifier; SourceState "stale" naming; dialect↔kind projection; docs/vnext/ledger.md absent; vault wiring; original review absent; run-2 scoring; unexercised contract promises). Real pytest/fastapi NOT RUN here; browser/keyboard/390px/screen-reader/physical-device NOT RUN.
NEXT: Put the §5 protected-code card in front of Rylee; nothing on the critical path (Steps 2-6) can start until it is answered.
```
