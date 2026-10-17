# Contracts audit — API type duplication and drift-gate consumption

**Issue:** #317 · **Date:** 2026-10-13 · **Scope:** read-only survey. No generated artifact,
no `src/` code and no `ui/` code was changed.

## What this document is, and is not

Per #317: *"This is a potential double source of truth, not evidence that API shapes are
currently wrong."* Nothing here is a defect report against the running product. The UI works
today. What follows is an inventory of where an API JSON shape is written down more than
once, and an answer to the narrower question #317 actually asks: **are the OpenAPI/client
drift checks consumed by anything?**

Per #317, no slice below is implemented here. They are recommendations only, to be taken up
after #267 Packet A inventory and ADR-0009 owner review. Per Rylee, 2026-10-13: *"Not yet.
Wanna get it cleaned up first then we design."*

---

## 1. Shape map — where each API JSON shape is written down

Six places carry API shapes. Only one of them is authoritative; only one is generated; none
of them are cross-checked against each other by any gate that runs in CI.

| # | Holder | Kind | Authority | Covers |
|---|--------|------|-----------|--------|
| 1 | `src/personal_world/worlds/*.py` (Pydantic + bare `dict[str, Any]`) | handwritten, canonical | **yes** | C1 config models; C2/C4/C6 response bodies as untyped dicts |
| 2 | `ui/src/generated/openapi.json` | generated (from #1) | no | 46 paths, method + query params, 2 error schemas, **0 response body shapes** |
| 3 | `ui/src/generated/api-types.ts` | generated (from #2) | no | TypeScript rendering of #2 — 2486 lines, `unknown` in 155 places |
| 4 | `ui/src/fd/types.ts` | handwritten | no | The UI's real view of every response shape |
| 5 | `ui/src/fd/api.ts` | handwritten transport | no | `as T` cast on every response — no runtime validation |
| 6 | `ui/src/fd/fixtures.ts`, `msw.ts`, `board-server.ts`, `companion/types.ts`, `edit-model.ts` | handwritten mocks | no | Test/Storybook shapes, typed against #4 |

### 1.1 The upstream cause: OpenAPI is empty by construction

`grep -rn "response_model" src/` returns **0 hits** across **67** route decorators
(`@app.get`/`post`/`put`/`delete`). Handlers return bare dicts:

- `src/personal_world/worlds/server.py:187-190` — `needs_you_route() -> list[Any]`
- `src/personal_world/worlds/cards.py:92` — `build(self, card_id: str) -> dict[str, Any] | None`
- `src/personal_world/worlds/memory_routes.py:44,48,59` — `-> list[dict]` / `-> dict`

With no `response_model`, FastAPI emits `additionalProperties: true` or `{}`. So
`ui/src/generated/openapi.json` has exactly two component schemas —
`HTTPValidationError` and `ValidationError` — and every 200 response body is
`{"type": "object", "additionalProperties": true}` or `{"items": {}}`:

```
$ python3 -c "import json; s=json.load(open('ui/src/generated/openapi.json')); \
    print(len(s['paths']), sorted(s['components']['schemas']))"
46 ['HTTPValidationError', 'ValidationError']
```

This is the finding that makes the rest of the audit inevitable: **the generated TS types
cannot describe a single API response body, so the handwritten `types.ts` is not
redundancy — it is the only place the body shapes exist.**

### 1.2 The generation chain, end to end

```
src/personal_world/worlds/production:create_app
  └─ scripts/gen-openapi.py            (writer)  → ui/src/generated/openapi.json
       └─ ui/scripts/generate-api-types.mjs       → ui/src/generated/api-types.ts
            └─ ???  (no importer)
```

- `scripts/gen-openapi.py:11-13` documents the intended consumer chain.
- `ui/package.json:15` — `build` runs `api:generate`, so `npm run build` refreshes
  `api-types.ts` from the *committed* `openapi.json`. It never re-derives the spec from
  Python.

### 1.3 Shape-by-shape, with the authoritative source

| API shape | Authoritative source | UI type | Mock type |
|---|---|---|---|
| C2 card envelope (`/api/cards/{id}`) | `cards.py:92-165` `build()` → untyped dict | `types.ts:18-37` `CardEnvelope` | `fixtures.ts` |
| C2 envelope meter | `cards.py:290-311` `_meter()` — emits `text_equivalent` + resolved numbers, omits unresolvable | `types.ts:13-16` `Meter` | `fixtures.ts` |
| C1 `Provider.auth` | `models.py:78-159` `Auth` | `types.ts:89-94` `Auth` | `msw.ts`, `fixtures.ts` |
| C1 `Request` | `models.py:240-305` `Request` | `types.ts:111-120` | `msw.ts` |
| C1 `Card` | `models.py:423-444` `Card` | `types.ts:128-138` `CardConfig` | `msw.ts` |
| C1 `Board` | `models.py:453-457` `Board` | `types.ts:55-59` `Board` | `board-server.ts:5` `ConfigDoc` |
| C1 `Action` | `models.py:460-477` `Action` | `types.ts:179-186` `ActionSummary` (derived, not the config) | `msw.ts` |
| C1 `Field_.format` enum | `models.py:312` | `types.ts:39` `Format` | — |
| Config kinds | `config_store.py:50-56` `MODEL_BY_KIND` (5) | `types.ts:87` `ConfigKind` (4) | `msw.ts:27` `Kind` (3) |
| C6 needs-you | `server.py:187-190` `list[Any]` | `types.ts:62-68` `NeedsYouEntry` | `fixtures.ts` |
| C4 memory rows | `memory_routes.py` untyped | `types.ts:210-276` `Memory*Row` | `fixtures.ts` |
| C4 board config item | `edit-model.ts:49` | `types.ts:49` `BoardItem` | `board-server.ts:5` |
| Companion API | `companion_routes.py` untyped | `fd/companion/types.ts` | `companion-server.ts` |

Two shapes are named `Meter` in two languages with **different meanings**:
`models.py:386-420` `Meter` is the C1 *config* (unresolved refs: `value` is a field key or
`$` path), while `types.ts:13-16` `Meter` is the C2 *envelope* (resolved numbers plus
`text_equivalent`). Both are correct; the collision is a rename hazard for any future
codegen.

### 1.4 Confirmed enum/form mismatches

These are **confirmed** — the two literals genuinely differ. Recording them is the deliverable;
fixing them is not.

| # | Shape | Backend | UI | Owner |
|---|---|---|---|---|
| **M1** | `Auth.type` | `models.py:102` — 6 values: `none \| bearer \| header \| basic \| cookie_session \| password_grant` | `types.ts:90` — 4 values: `none \| bearer \| header \| basic` | **#320** (per #317) |
| **M2** | `Auth` fields | `models.py:106-111` — `login_path`, `username_field`, `password_field`, `token_path`, `token_field` | `types.ts:89-94` — none of them declared | **#320** (same slice) |
| **M3** | `Field_.format` | `models.py:312` — 7 values, includes `"count"` | `types.ts:39` `Format` — 6 values, no `"count"` | #317 follow-up |
| **M4** | Config kinds | `config_store.py:50-56` — `provider, request, card, board, action` | `types.ts:87` `ConfigKind` — 4, **no `board`** | #317 follow-up |
| **M5** | Config kinds (mock) | same 5 | `msw.ts:27` `Kind` — 3, **no `board`, no `action`** | #317 follow-up |

M1 is the one named in #317 and is carried here unchanged: *"a narrower `Auth.type` union
than `src/personal_world/worlds/models.py` (backend supports `cookie_session` and
`password_grant`); record this as a confirmed enum/form mismatch, fix owned by #320."*

**M1/M2 are benign today**: `Provider` objects are only ever *round-tripped*, never
constructed with `cookie_session` in the UI, so nothing is broken. They become a live bug the
moment the Connect editor offers those auth types. **M4 is the one with reach today**: the UI
cannot read or write `/api/config/board` or `/api/config/action` through the Connect path, so
a board or action configured outside the UI never round-trips back through it.

---

## 2. Which files compile-import the generated types

**Answer: none. Zero files import `ui/src/generated/api-types.ts`.**

```
$ grep -rn "api-types" ui/src ui/e2e ui/uat ui/kit --include=*.ts --include=*.tsx
ui/src/generated/api-types.ts:2: * This file was auto-generated by openapi-typescript.
```

The only hit is the generator's own self-description in the file header. There are no
`import type { paths } from "../generated/api-types"` sites, and consequently:

- **`openapi-fetch` is a declared dependency with zero call sites.** The one textual match in
  the tree is a comment in `ui/src/test/setup.ts:4`.
- The `tsconfig.app.json` include almost certainly still compiles `api-types.ts` (it lives
  under `src/`), so the 2486 lines are typechecked but never *used*. Whether `tsc -b`
  includes it was **not** verified here — no Node toolchain in the audit sandbox (§4).
- `ui/README.md:40` and `ui/README.md:104` still advertise the typed client as live. That
  documentation is now aspirational.

### What *is* compile-imported

The handwritten set — this is the real consumer list:

```
ui/src/fd/api.ts              ui/src/fd/fixtures.ts        ui/src/fd/home-model.ts
ui/src/fd/Connect.tsx         ui/src/fd/msw.ts             ui/src/fd/prefs-core.ts
ui/src/fd/Home.tsx            ui/src/fd/use-board-edit.ts  ui/src/fd/edit-model.ts
ui/src/fd/Memory.tsx          ui/src/fd/board-server.ts    ui/src/fd/companion/api.ts
ui/src/fd/Meter.tsx           ui/src/fd/companion/companion-core.ts
ui/src/fd/Row.tsx             ui/src/fd/companion/presentation.ts
ui/src/fd/Settings.tsx        ui/src/fd/companion/CompanionPanel.tsx
ui/src/fd/Strip.tsx           ui/src/fd/companion/CompanionProvider.tsx
ui/src/test/connect.test.tsx
```

**16** files import `fd/types` (15 under `ui/src/fd/`, plus `ui/src/test/connect.test.tsx`,
which reaches it as `"../fd/types"`); **5** more import `fd/companion/types`. Replacing
`types.ts` is therefore not a one-file change, and any replacement must land with these call
sites intact.

### The transport has no runtime check

`ui/src/fd/api.ts:52`:

```ts
return (await res.json()) as T;
```

Every response is trusted by assertion. `ApiError` (`api.ts:26-36`) classifies *transport*
failures only — a `200` with a malformed body is handed to the UI as `T`. So the handwritten
types are load-bearing for correctness, and there is no second line of defence that would
catch M1–M5 at runtime. This is the strongest argument for keeping the TS types *close to* a
generated source rather than deleting them.

---

## 3. Are the drift checks consumed? (#317's actual question)

### 3.1 `scripts/contract-drift-check.py` — **not consumed**

The script says so itself at line 25-26:

> `No CI wiring: this gate is armed by Rylee's tap, not by tonight (plan rails).`

Verified rather than assumed:

```
$ grep -rn "contract-drift\|gen-openapi\|openapi" .github/
(no output)
```

`.github/workflows/` contains `ci.yml`, `codeql.yml`, `publish-image.yml`, `uat-live.yml`,
`validate.yml`. **None of the five mentions `contract-drift-check.py` or `gen-openapi.py`.**
`ui-ci` runs four gates — token drift, kit drift, typecheck, lint, tests, build — and the
Python API gates are not among them. The docstring's claim is accurate.

There is also no test asserting the gate. Exactly one file in `tests/` mentions OpenAPI at
all — `tests/recipes/test_openapi_import.py`, the recipe importer — and it does not touch
`contract-drift-check.py`.

### 3.2 `scripts/gen-openapi.py` — consumed only by hand

Its sole consumer is a human running it to refresh the committed spec after a Python change.
The chain stops there: nothing re-runs it, so a Python shape change never reaches
`openapi.json`, and therefore never reaches `api-types.ts`.

### 3.3 `ui/scripts/generate-api-types.mjs` — consumed, output discarded

Unlike the other two, this one *is* wired: `ui/package.json:15` runs it inside `npm run build`,
which `ci.yml:127-129` runs. But:

- Its output is imported by nothing (§2).
- `npm run build` runs it **after** the token drift gate (`ci.yml:97-105`) and does not
  `git diff --exit-code` afterwards, so a regenerated `api-types.ts` that differs from the
  committed copy is not caught.
- Its input is the committed `openapi.json`, never the live app.

### 3.4 Drift-guard failure receipt

Proving the guard *would* fire matters as much as showing that it does not. The audit
sandbox has no `uv`, no Node, and no network (`pip download fastapi` →
`ProxyError: Tunnel connection failed: 403 Forbidden`), so the live-app boot half of the gate
cannot run here — **the guard is demonstrated on its compare core, not end to end.**

`/tmp/drift-receipt/prove_drift_guard.py` imports `_dump()` *from the real
`scripts/contract-drift-check.py`* by path (no repo file is written or modified), then feeds
it the committed spec twice: once unchanged as a control, once with a synthetic shape change —
`/api/needs-you`'s 200 body narrowed from `{"items": {}}` to a strict required-properties
object, the shape a real `response_model=` addition would produce.

```
$ python3 -I /tmp/drift-receipt/prove_drift_guard.py; echo "HARNESS EXIT=$?"
[control]  _dump(committed) == committed bytes : IDENTICAL
[mutation] schema before : {"items": {}, "title": "Response Needs You Route Api Needs You Get", "type": "array"}
[mutation] schema after  : {"type": "object", "title": "...", "properties": {"items": {...}}, "required": ["items"]}

contract drift check (read-only)  -- replay of the guard's compare step
  spec       : DRIFT (live paths: 46, committed: 46)

               run `uv run python scripts/gen-openapi.py` to regenerate the committed OpenAPI document

RESULT: DRIFT
exit code the guard would return: 1

--- byte diff (guard is a whole-document string compare) ---
--- committed
+++ mutated
@@ -1769 +1769,11 @@
-                  "items": {},
+                  "properties": { ... "required": [ "items" ...
HARNESS EXIT=1
```

Two things this receipt establishes:

1. **The serializer is sound.** `_dump(committed)` reproduces the committed
   `openapi.json` byte-for-byte, so the control is clean and the mutation is the only
   variable. The committed spec is genuinely in sync with the writer's serialization.
2. **The guard is byte-strict and would catch this.** A single response-schema narrowing
   flips `RESULT: CLEAN` → `RESULT: DRIFT` and exit `0` → `1`, with the regeneration
   instruction printed.

Note the guard's blind spot, which the receipt makes visible: it reports `DRIFT` for a change
in a schema that carries no shape anyway (`{"items": {}}` → a strict object). It is a
whole-document string compare, so it will fire on reflow, key-order and title changes too.
That is correct for a "did the app change?" tripwire, and it is why it must never be wired
to something that rewrites the file automatically.

### 3.5 Verdict on #317

**The gates are not consumed.** One of three (`generate-api-types.mjs`) runs in CI but has no
consumer for its output; the two that carry the real signal (`contract-drift-check.py`,
`gen-openapi.py`) are manual-only, exactly as the docstring admits. The consequence is that
the generated layer is a *dead branch*: it is regenerated into a file nothing reads, and it
is gated against nothing. Today the UI's `types.ts` is the de facto source of truth, and the
only person who notices a mismatch is a human who happens to run the script.

---

## 4. What could not be verified here

Recorded so the coordinator does not over-read this audit.

- **The live-app half of `contract-drift-check.py` was not run.** No `uv`, no FastAPI, no
  network. The claim "committed `openapi.json` is in sync with the live app" is therefore
  **inferred**, from the byte-identical `_dump` control plus the file's last-regeneration
  commit — not observed.
- **`scripts/gen-openapi.py` and `ui/scripts/generate-api-types.mjs` were not run.** The
  second shells out to `npm exec --yes openapi-typescript@7.13.0`, which needs the network.
- **Whether `tsc -b` actually includes `api-types.ts` in `tsconfig.app.json`** — needs Node.
  The consequence (dead-but-typechecked 2486 lines) holds either way; only the cost changes.
- **A pytest run was not possible** (pytest and the runtime deps are unavailable), so no
  Python test result backs the model citations. Every Python line reference in §1.3 was read
  directly from the source at the stated line.

### The one test that does cover this change

The only repo test affected by adding a Markdown file is `tests/test_docs.py` — its
`test_internal_links_resolve` is parametrized over **every** `.md` in the repo, so the new
document is inside its blast radius. pytest cannot be installed offline, so
`/tmp/drift-receipt/run_test_docs.py` execs the **real** `tests/test_docs.py` source with a
stdlib `pytest` stub and calls both test bodies:

```
$ python3 -I /tmp/drift-receipt/run_test_docs.py; echo "EXIT=$?"
PASS  test_canonical_files_exist
INFO  _markdown_files() collected 229 .md files, including docs/vnext/contracts-audit.md
PASS  test_internal_links_resolve  (229 files, incl. the new doc)
EXIT=0
```

Both pass. This document contains no Markdown links at all, so the link resolver has nothing
to resolve for it.

No generated artifact was modified: `git status --porcelain` after all gate work reports only
`docs/vnext/contracts-audit.md`, and `git diff HEAD -- ui/src/generated/ src/ ui/src/ scripts/ .github/`
is empty.

---

## 5. Risk-ranked replacement order

Smallest-deletion-first. Each slice is independently landable, none is implemented here, and
all await #267 Packet A inventory and ADR-0009 owner review.

| Rank | Slice | Size | Risk if done | Why this order |
|---|---|---|---|---|
| **1** | **Land M1/M2 into #320** — widen `types.ts:89-94` `Auth` to the six-value backend union and declare `login_path` / `username_field` / `password_field` / `token_path` / `token_field`. | 1 interface, no call-site churn | **very low** — additive; optional fields only, no existing object becomes invalid | Removes the one confirmed mismatch #317 named. Fully inside #320's ownership. **Do this first: it is the only slice with a real bug behind it.** |
| **2** | **Land M3/M4/M5** — add `"count"` to `Format`; add `"board"` to `ConfigKind`; add `"board"`/`"action"` to the msw `Kind`. | 3 one-line unions | **low** — widening unions; the `board`/`action` additions are opt-in | Cheap, and M4 unblocks board/action round-tripping. Same file, same review. |
| **3** | **Fix the false documentation** — `ui/README.md:40,104` advertise a typed client that has zero consumers. | doc only | **none** | Zero code risk, removes a claim that sends the next reader hunting. Cheapest real win in the list. |
| **4** | **Delete or archive `ui/src/generated/api-types.ts`** and drop `api:generate` from `ui/package.json:15`. | delete 2486 lines + 1 script line + 1 dep (`openapi-fetch`) | **low-medium** — nothing imports it, but `openapi.json` must stay (the drift gate's input) | This is the *smallest deletion* available and it removes a dead branch. **Hold until #4 lands**, since it deletes the thing a future codegen path would replace. |
| **5** | **Give the spec a body**: add `response_model=` to the highest-traffic routes — `/api/boards/home`, `/api/needs-you`, `/api/cards/{card_id}`, `/api/memory/find`, `/api/connect/try`. | 5 route decorators | **medium** — changes the emitted spec, which the byte-strict guard treats as drift; requires a coordinated regen | This is the *only* slice that makes `api-types.ts` capable of carrying body shapes. Without it, slices 4+ buy nothing. **Must not precede the #267 inventory.** |
| **6** | **Wire `contract-drift-check.py` into `ci.yml`**, as a read-only step alongside the token drift gate. | ~8 workflow lines | **medium** — will go red on any stale spec; needs `create_app` to boot in CI and needs deps installed | Converts the audit's §3 verdict from "not consumed" to "consumed". Highest value, and deliberately **not** first: wiring a gate that has never run in CI will surface accumulated drift immediately. |
| **7** | **Point `ui/src/fd/types.ts` at the generated types**, or add a CI step asserting the two agree, keeping the handwritten names as aliases. | large; touches 16 importers of `fd/types` | **high** — this is the cross-language schema change #317 forbids in this ticket | Explicitly out of scope for #317: *"No mass rename, no breaking cross-language API/schema change or automatic semantic-kernel adoption in this ticket."* Listed only so the coordinator sees the end state. |

### The dependency that matters

Slice 4 without slice 5 deletes dead weight. Slice 5 without slice 4 creates a second dead
branch. **Slice 5 must land before anything re-points the UI at generated types** — until the
spec carries response bodies, `api-types.ts` has nothing to offer `types.ts` that `types.ts`
does not already say better.

And per #317, none of 4–7 starts until #267 Packet A inventory is done and ADR-0009 has owner
review.

---

## Appendix — commands run

```
grep -rn "response_model" src/ | wc -l                       # 0
grep -rn "@app\.\(get\|post\|patch\|delete\|put\)" src/personal_world/worlds/*.py | wc -l   # 67
grep -rn "api-types" ui/src ui/e2e ui/uat --include=*.ts --include=*.tsx
grep -rn "contract-drift\|gen-openapi\|openapi" .github/    # no output
grep -rn "openapi-fetch" ui/src ui/e2e ui/uat | wc -l        # 1 (a comment)
python3 -c "import json; s=json.load(open('ui/src/generated/openapi.json')); print(len(s['paths']), sorted(s['components']['schemas']))"
python3 -I /tmp/drift-receipt/prove_drift_guard.py          # exit 1, RESULT: DRIFT
python3 -I /tmp/drift-receipt/run_test_docs.py               # exit 0, both tests PASS
git status --porcelain                                       # only docs/vnext/contracts-audit.md
```