# Connect contract — independent re-review (b-rereview)

**Reviewer:** deepseek-v4.1-flash. **Author of the revision under review:** MiniMax (per `## Revision 1` and the packet).
Different model family, as the routing decision of 2026-10-13 requires: "No model grades only its own output: a
reviewer or verifier is a different family from the author."

**Tip reviewed:** the revision commit `cc612ed` ("docs(vnext): revise the Connect contract against its review"),
tree of this clone. `docs/vnext/connect-contract.md` is 837 lines.

**Method.** Every verdict below was reached by opening the named file and line in this clone, not by reading the
revision's own `## Revision 1` table. The revision repeatedly cites `786f506`; the only vnext change since then is
`51ef662` (original contract) and `cc612ed` (the revision), so the cited source lines are checked against the
working tree. Where the revision's row and the file disagree, the file wins.

**One structural fact that bears on the whole review.** `## Revision 1` states (contract line 812) that the
original review file "was **not present** in the worktree this revision was made in", so it could not match the
original four MINOR and two NIT findings and substituted six self-found ones (rows `MINOR-1..4`, `NIT-1..2`).
That is disclosed honestly and is not scored as a defect of the document; it is recorded here because it means
the revision's MINOR/NIT rows are **not** a resolution of the original MINOR/NIT findings.

---

## 1. Verdict on the original BLOCKER + 3 MAJORs

| Id | Original finding | Verdict | Evidence I checked myself |
|---|---|---|---|
| BLOCKER-1 | Contract requires persisted state (`ConnectionDescriptor`, `Capability`/`ReadSpec`, `PublishSelection`, `ActionProposal`, last-good values) with no declared home, while §6/§7.1 asserted "no new field/file/model/table". | **PARTLY** | The structural fix **did** land. New §6.1 ("What v1 persists, and where", contract `docs/vnext/connect-contract.md:420`–`:459`) gives each type a home in the existing C1 files, and §7.1 now names the exceptions and points at §6.1 (`:521`–`:526`); §1 defines "durable" (`:40`–`:43`). But the narrowed headline claim — "**exactly four** additive optional model fields" (`:426`–`:428`) — is contradicted by §6.1's own persisted row for `CredentialReference.rotated_at`, which is said to live "in the provider file, if the owner sets it" (`:458`) while `Auth` (`src/personal_world/worlds/models.py:78`–`:101`) has **no** `rotated_at` and `extra="forbid"` (`models.py:101`). That is a persisted value whose "not new" claim is false — the same class of defect as the original BLOCKER, just one field smaller. See **NEW-2**. |
| MAJOR-a | §7.3 verifier-gap wording wrong: it claimed a Project Home approval id is "stored but not verified"; in fact `dispatcher.py:277-278` raises `NotPermitted` and stores nothing. | **RESOLVED** | `src/personal_world/worlds/dispatcher.py:275` is `def record_project_home_approval`; `:277` is `if self._ph_verify is None:`; `:278` is `raise NotPermitted("Project Home approval is not available")`; the `with self._db.write_tx()` that would write opens **after** at `:280`. Nothing is stored, and the raise precedes the transaction. §7.3 (`docs/vnext/connect-contract.md:585`–`:600`) now quotes those exact two lines, states the write transaction has not opened, calls the earlier wording "wrong in the unsafe direction", and notes the answer route returns 403. The route's 403 is real: `src/personal_world/worlds/room_routes.py:76` maps `NotPermitted` to `HTTPException(status_code=403)`. §5.1 (`:395`), §5.2 (`:405`), §9 (`:779`–`:781`) and §10 (`:800`) are consistent with the corrected wording. The revision also correctly keeps `production.py:95` as the missing-verifier evidence (`dispatcher = Dispatcher(db, app.state.store, secret_values=live)` — no `project_home_verifier`). |
| MAJOR-b | §4 field ledger omitted `CardDraft`, `Capability` and `ReadSpec`, so those types had no named consumer / reason / security test. | **RESOLVED** | New **§4.7 `CardDraft`** (`docs/vnext/connect-contract.md:335`–`:350`) and **§4.8 `Capability` and `ReadSpec`** (`:352`–`:371`) exist, each with a Consumer / Reason / Security-test row per field. The C1 targets they point at are real: `Card.title`/`meaning`/`fields`/`meter`/`status` at `src/personal_world/worlds/models.py:425`,`:431`–`:434`, and `Request.query`/`ttl_s`/`timeout_s`/`max_bytes`/`mode` citations resolve (`models.py:245`,`:250`,`:184`,`:185`,`:357`). §4.1's `capabilities` row cross-references §4.8 (`:276`). Two modelling wrinkles remain (see **NEW-3**, **NEW-7**), but the omission is closed. |
| MAJOR-c | Endpoint 12, `POST /api/connect/v1/approvals/{authorization_id}/record-external`, does not exist. | **RESOLVED** | Endpoint 12 is now the **existing** route: `POST /api/rooms/{provider_id}/actions/{room_action_id}/answer`, decorated at `src/personal_world/worlds/room_routes.py:52` (`def answer_need` at `:53`), body field `project_home_approval_id` read at `:72`. The route reaches `room0.answer` (`src/personal_world/worlds/room0.py:581`) which calls `dispatcher.record_project_home_approval` for a Project Home-governed provider with an id (`room0.py:598`–`:599`) and otherwise `dispatcher.approve` (`room0.py:600`). The contract's endpoint-12 row (`docs/vnext/connect-contract.md:251`) and §9 step 6 (`:773`–`:776`) match the code, the "there is no separate Connect endpoint" note is accurate, and the table footer no longer claims both 11 and 12 would move under `/api/connect/v1/` (`:255`–`:258`). |

No original MAJOR or BLOCKER is left **not resolved** in its literal claim; the single PARTLY is BLOCKER-1.

---

## 2. New findings in the revision

Each is tagged and carries the § or `path:line` I opened.

### NEW-1 — MAJOR — §6 asserts "there is no results or history table"; a `history` table exists

`docs/vnext/connect-contract.md:479` (the `worlds.db` tables row) ends: "**no table added**, and there is **no
results or history table** in this database, which is why `TestResult` is not persisted (§6.1)". §4.3 repeats
the claim (`:294`: "There is no results or history table behind it"). There **is** a `history` table — an
append-only audit log with immutability triggers — and an FTS index, both in `worlds.db`:

- `src/personal_world/worlds/memory_store.py:56` — `CREATE TABLE history (`
- `:59`–`:60` — the `history_no_update` / `history_no_delete` triggers
- `:61` — `CREATE VIRTUAL TABLE find_index USING fts5(`
- `:385`,`:396` — the store reads `history` as a first-class table (`TABLES + ("history",)`)
- `src/personal_world/worlds/production.py:132` — `memory = MemoryStore(db)`, and `:64` builds that `db` with
  `Database.in_dir(data_dir)`, i.e. the one `worlds.db` (`src/personal_world/worlds/db.py:17`).

This is also a **regression**: the pre-revision document correctly listed `history` in this row
(`git show 51ef662:docs/vnext/connect-contract.md`, line 388: "`worlds.db` tables | `authorizations`,
`executions`, memory, history"). The revision's own `MINOR-1` row asserts "There is none" and removes it. The
`history` table is an audit log for `kept`/`later`/`records`, not a test-results store, so the conclusion
("do not persist `TestResult`") may still hold — but the stated reason is false and the table list is
incomplete, in the exact section that the BLOCKER fix rests on. It should say: no **results** table; a `history`
audit table and a `find_index` FTS table do exist and are not usable for `TestResult`.

### NEW-2 — MAJOR — "exactly four" optional fields is short by one (`rotated_at`)

§6.1's headline narrows the old blanket claim to "**exactly four** additive optional model fields"
(`docs/vnext/connect-contract.md:426`–`:428`), enumerated as `Auth.scope`, `Request.provenance`,
`Request.verified`, `Action.state` (`:443`–`:448`). But the "not persisted" table says
`CredentialReference.rotated_at` lives "the provider file, if the owner sets it" (`:458`), and §4.2 says the
same (`:288`). The provider file is the `Provider`/`Auth` model, and `Auth` has no `rotated_at`:

- `src/personal_world/worlds/models.py:78`–`:101` — `Auth` fields are `type`, `secret_ref`, `header_name`, and
  the cookie/grant fields; no `rotated_at`.
- `models.py:101` — `extra="forbid"`, so the file cannot carry an undeclared key.
- `grep -n rotated_at src/personal_world/worlds/models.py` → no match.

So either `rotated_at` is not persisted (and `:458`/`:288` are wrong), or it is a fifth additive optional field
(and "exactly four" is wrong). Either way the narrowed claim that is the whole BLOCKER resolution does not hold.
`published_at` (NEW-4) is a second candidate for the same gap, which is why BLOCKER-1 is PARTLY, not RESOLVED.

### NEW-3 — MINOR — capability-level `provenance`/`verified` are persisted on a per-`Request` field

§2 and §4.8 define `provenance` and `verified` on `Capability` (`docs/vnext/connect-contract.md:119`–`:120`,
`:363`–`:364`), and §4.8's rows name the capability as the thing that is "never `verified` until a foreman
checks it". §6.1 then persists them on `Request` (`:435`: "two optional fields: `provenance`, `verified`"),
because a `Capability` maps to a `ReadSpec[]`. A capability with more than one read — which §2 explicitly
allows (`reads: ReadSpec[]`, `:118`, non-empty by §4.8 `:362`) — has no single place for a capability-level
`verified`. The mapping needs to be stated (per-capability on the card, or one read per capability) or the
model is ambiguous about which of a capability's requests carries its verified flag.

### NEW-4 — MINOR — `PublishSelection.published_at` / `published_by` have no declared home

§4.4 lists the consumer of `published_at` and `published_by` as "History"
(`docs/vnext/connect-contract.md:311`). §6.1's persisted table for `PublishSelection` (`:438`) assigns only
`Board.items`, `BoardItem.hidden` and the card's `fields`, and the "not persisted" table (`:450`–`:459`) does not
mention them. There is no history table that could receive them (NEW-1) and no field named for them, so
"History" is a consumer with nothing behind it. Either give `published_at` a field/home or drop it; NIT-2 of the
revision claims these are handled but only explains `published_by` ("owner by construction"), not where
`published_at` is written.

### NEW-5 — MINOR — `ConnectionDescriptor.principal` (object) vs stored `principal_id` (string)

§2 types `principal` as `PrincipalBinding | null` (`docs/vnext/connect-contract.md:94`,`:105`), and §9 shows it
as an object: `"principal": { "person_ref": "your-person-id" }` (`:727`). §6.1's identity row claims the
descriptor adds "no" new state and maps to `providers/<id>.yaml` (`Provider`) (`:434`). But `Provider` stores
`principal_id: str | None` (`src/personal_world/worlds/models.py:180`), not an object, and §4.1's row says the
value is "Pattern-validated at save and again at send (`confinement.py:606`)" — which matches the string form.
The object shape in §2/§9 therefore needs either a stated projection onto `principal_id` or a declared field.

### NEW-6 — NIT — off-by-one citation for the JSONPath subset

§4.7 cites the JSONPath save-time check as `models.py:25` (`docs/vnext/connect-contract.md:347`). Line 25 is
blank; the function is `_check_path` at `src/personal_world/worlds/models.py:26`. §3 endpoint 7 cites the right
line (`:246`, `models.py:26`); §4.7 should match.

### NEW-7 — NIT — §6.1 says `timeout_s` "stays on the provider", but `Request.timeout_s` exists

§6.1's `ReadSpec` row writes that the `Request` fields are "`method`, `path`, `query`, `ttl_s`, `assertions`;
`timeout_s`/`max_bytes` stay on the provider" (`docs/vnext/connect-contract.md:435`). `Request` does carry
`timeout_s: float | None` (`src/personal_world/worlds/models.py:251`); only `max_bytes` is provider-only
(`models.py:185`; `ReadSpec.bounds.max_bytes` has no `Request` counterpart). §4.8 itself relies on the
request-level override (`:369`, "Must be ≤ the provider's `timeout_s`").

### NEW-8 — NIT — the original review's four MINOR + two NIT are not addressed

The revision discloses (contract line 812–818) that it could not read the original review's MINOR/NIT findings
and substituted its own `MINOR-1..4` / `NIT-1..2`. Those six rows are therefore not a resolution of the
original six; the coordinator must re-run the match against the review it holds. This is honestly stated, so it
is a NIT on the deliverable, not a hidden defect.

---

## 3. What is genuinely good here

- The verifier-gap correction (MAJOR-a) is exact: the raise precedes the transaction, and the revision changed
  the claim in the *safe* direction and re-quoted the code rather than softening it. Verified at
  `dispatcher.py:277`–`:278` vs the write at `:280`.
- Endpoint 12 (MAJOR-c) was fixed by *replacement with the live route*, not by inventing a path — the right call
  under decision #319 ("Worlds shows/links, never mints competing authority") and #321 ("new because 'new'" is
  ruled out). The route, body field, dispatch call and 403 all resolve in the tree.
- The citation discipline is materially better than the original: I spot-checked ~60 `path:line` cites across
  `confinement.py`, `config_store.py`, `production.py`, `room0.py`, `recipes.py`, `framework.py`, `server.py`,
  `room_routes.py`, `actions_routes.py`, `seed.py` and `Connect.tsx:711` / `api.ts:180`; all resolved to the
  claimed construct except the two NITs above.
- §6.1's separation of *persisted* from *deliberately not persisted* is exactly the shape the original BLOCKER
  asked for; the enumeration is short by one field, not wrong in kind.

---

## 4. Findings count

Counted over the **new findings in the revision** (§2). The verdicts in §1 are a separate score.

FINDINGS: 8 (BLOCKER x0, MAJOR 2, MINOR 3, NIT 3)
