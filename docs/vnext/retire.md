# vnext / s0-retire — the keep-or-retire ledger

> **Status:** Current · **Verified:** 2026-10-13 · **Canonical for:** what was retired from `personal-world` as provably dead, the consumer proof for each retirement, and its rollback · **Read this if:** you are auditing a deletion, or you want to know which zero-consumer code is deliberately still here.

**In short:** cleanup ran before design. Seven units were removed, one commit
each, every commit carrying its consumer proof and its rollback command.
Everything else with zero consumers is listed below as **kept** — protected
code, contract vocabulary, and decision-bound surfaces are named, not
removed. The next lane can read this file instead of re-deriving the search.

## The bar a retirement had to clear

A unit (a module, a file, or a single export) was retired only when **all**
of the following were provable at the commit:

1. **No importer.** No `import` / `from … import` of it anywhere under
   `src/`, `ui/`, `tests/`, `scripts/`. Checked with an AST import graph
   over every `.py` in those trees, not only with grep — so an import that
   greps clean because of line wrapping still counts.
2. **No reference at all.** `grep -rn "\b<name>\b"` over `src`, `ui/src`,
   `ui/e2e*`, `tests`, `scripts`, `docs`, `.project`, `config`, `design`
   returned no hit outside the definition itself.
3. **No route registration.** Not named in `api.py`, not passed to
   `register_*_routes`, not reachable from any entry point
   (`personal_world.cli:main`, `worlds/production:create_app`).
4. **No dynamic import or introspection path.** The repository's only
   `importlib.import_module` call is `worlds/db.py:122`, whose module list
   is the fixed tuple `("authn", "dispatcher", "memory_store")`. There is
   no `dir()`, `getmembers()`, or `__subclasses__` anywhere in `src` or
   `tests`, and every `getattr()` uses a literal attribute name. So
   "zero grep hits" really does mean zero reachable callers.
5. **No test that exists only to keep it.** Where a test named the unit,
   the unit was not retired.

## Retired — one commit per unit

Each row is independently revertable. `git revert <sha>` restores the file
exactly; no later commit depends on any of these deletions.

| # | Unit retired | File | Consumer proof (one line) | Rollback |
|---|---|---|---|---|
| 1 | `ChatProviderRegistry` (class + 5 methods) | `src/personal_world/chat_registry.py` | Zero importers across `src`/`ui`/`tests`/`scripts`; the only pre-existing hits were the definition and prose in [ORPHANS.md](../surfaces/ORPHANS.md) (PROV-031, `ORPHAN`) and [PROVIDER-MATRIX.md](../surfaces/PROVIDER-MATRIX.md) (`NO (orphan)`). No test names it. | `git revert 59445d39ca596c8a3815487222150f473c25a9e7` |
| 2 | `known_system(system_id)` | `src/personal_world/briefing.py` | Zero importers. Both live call sites validate inline against the exported `SYSTEM_IDS` (`api.py:2849`, `api.py:3593`), so the "re-exported for the route's place validation" wrapper is a leftover of an earlier route shape. | `git revert dd020137f6b237ccb2444e31c5083089e8df6491` |
| 3 | `dumps_place(system, item_id, updated_at)` + its now-orphan `import json` | `src/personal_world/briefing.py` | Zero importers, zero references, zero routes. `build_briefing` receives place data as injected plain dicts; nothing serialises a place through it. `import json` had no other user in the module after the cut (ruff F401). | `git revert 56289a8ddeec2c46b45ae66bd303825b32312e5f` |
| 4 | `CONTRAST_FLOOR = "comfortable"` | `src/personal_world/prefs.py` | Zero references anywhere. Superseded by the canonical `prefs.CONTRAST.floor = "comfortable"` (`EnumPref`, `prefs.py:179-183` at this commit), which is what the module's own floor check reads. `tests/test_prefs_schema_parity.py` pins `prefs.CONTRAST.allowed`/`.default`, never this constant. | `git revert 79872c0df35ed2ec146bfba54baea7a55dd3d0e6` |
| 5 | `TEXT_SCALE_FLOOR = 1.0` | `src/personal_world/prefs.py` | Zero references anywhere. Superseded by the canonical `prefs.TEXT_SCALE.floor = 1.0` (`NumberPref`, `prefs.py:183-187` at this commit). | `git revert 9eb6b3541235a11bb74576559f3c498791704339` |
| 6 | `DENSITY_FLOOR = "compact"` | `src/personal_world/prefs.py` | Zero references anywhere. Superseded by the canonical `prefs.DENSITY.floor = "compact"` (`EnumPref`, `prefs.py:187-191` at this commit). The known schema-vs-backend density drift that `test_prefs_schema_parity.py` documents belongs to the schema JSON and the `EnumPref`, not to this constant. | `git revert 9352b0d6f410591510009680bad0d87515e05c42` |
| 7 | `PushHub.status_word()` + its now-orphan `from .status import Status` | `src/personal_world/push.py` | Zero callers. Not an override point — `PushHub` has no subclass (`grep -rn "PushHub)" src tests` → no matches). What it computed stays available from the live surface: `configured()` (`push.py:620`) plus `status.py`'s own `Status.HEALTHY` / `Status.NOT_CONFIGURED` mapping (`status.py:5,12,26`). | `git revert c9741a3a5482fac15b8a1da2b1f2b5fa26359faa` |

To roll back everything at once, revert in reverse order:

```
git revert c9741a3 9352b0d 9eb6b35 79872c0 56289a8 dd02013 59445d3
```

This ledger file is itself reverted with
`git revert $(git log --format=%H -1 -- docs/vnext/retire.md)`.

## Kept — protected code, named but NOT removed

These have zero consumers in exactly the sense the bar above describes.
They stay because protected code is the owner's alone and needs a picker
card first (see "Decisions in force" below). **Do not delete them from a
cleanup lane.**

| Unit | File | Why it is held |
|---|---|---|
| `SessionStore.invalidate_all` | `src/personal_world/worlds/authn.py:126` | **Auth.** Session-store invalidation is owner-only surface. |
| `get_proposal(proposal_id, store)` | `src/personal_world/tool_registry.py:1254` | **At-most-once actions.** The durable proposal is the audit record for an approved write; its accessor is part of that machinery, not dead weight. |
| `get_record(world, category, record_id)` | `src/personal_world/records.py:209` | **Records/receipts surface.** The Records API is documented in [RECORDS-API.md](../RECORDS-API.md); the absence of a current caller is a routing gap to close with the owner, not a deletion. |
| `SopsBroker` (+ `list_keys`) | `src/personal_world/providers/adapters.py:228` | **Secrets.** [ARCHITECTURE.md](../ARCHITECTURE.md) names it a deliberate pipe-to-consumer path, and [COHERENCE-DECISION-PREP.md](../surfaces/COHERENCE-DECISION-PREP.md) says to *keep* it as the future replaceable-provider seam. |
| `SOPSVaultAdapter` | `src/personal_world/vault.py:233` | **Secrets/vault**, same keep-for-later decision. |
| `ThemePackRegistry.resolve_companion` | `src/personal_world/theme_pack.py:106` | **Art/canon.** Companion resolution is the art surface. |
| `execution_viewer.py` (whole module: `ExecutionViewer`, `ExecutionStore`, `ExecutionRecord`) | `src/personal_world/execution_viewer.py` | **Execution receipts**, *and* decision-bound: `.project/DECISIONS.md` records "**`ExecutionViewer` stays its own executions view for now** (store convergence = a later named call)". It has zero consumers since `app.py` stopped instantiating it, but an owner decision says to keep it. Named as ORPHAN in [ORPHANS.md](../surfaces/ORPHANS.md) (STORE-020) and [REPOSITORY-INVENTORY.md](../repo/REPOSITORY-INVENTORY.md) (ORPH-05). |
| `cli_dispatch.py` (whole module, 2399 lines) | `src/personal_world/cli_dispatch.py` | **Decision-bound CLI surface.** This is owner decision #19's `api-manifest` / `api METHOD PATH` / `do NOUN VERB` surface. `cli.py:main` today registers only `framework validate`, `framework validate-packs`, `memory backup`, `memory restore`, so the module has zero importers — but its own module docstring says "Retiring the legacy verbs onto this surface is an owner decision, not a lane-local one", and it carries the auth / OIDC / prefs / journal / proposal verbs. Removal is a contract decision, not a cleanup. |

## Kept — contract vocabulary with zero consumers

These are read by nobody today but name a rule of a published contract.
Deleting them would delete the statement of the rule, so they stay until
the contract itself is retired.

| Unit | File | The rule it states |
|---|---|---|
| `CARD_TONES` | `src/personal_world/rooms.py:252` | room/0 rule 3: the three card tones the contract names. Its siblings `ROOM_STATUSES`, `SUPPORTED_CONTRACTS`, `UNREACHABLE`, `INCOMPATIBLE` are all live. |
| `CHANGED_PATH = "/changed"` | `src/personal_world/worlds/room0.py:96` | The room/0 out-of-band change signal. `parse_changed` documents the `/changed` ping by name (`room0.py:109-112`). |
| `SITUATIONS` | `src/personal_world/briefing_voice.py:23` | "The situation vocabulary every resident table must cover" (`worlds-briefing/1`). |
| `EXIT_DRIFT = 3` | `src/personal_world/envelope.py:8` | Completes the exit-code vocabulary beside `EXIT_OK`/`EXIT_ERROR`/`EXIT_DENIED`. |
| `ObservedState` | `src/personal_world/providers/native_reconciler.py:44` | The observed-state half of the reconciler pair (`ObservedState` / `DriftItem`); its absence is the documented TOOL-013 gap ("Observed state not available for diff"), i.e. missing wiring, not dead code. |
| `LEGACY_PREFIXES = ("station", "vnext")` | `src/personal_world/station_ui.py:131` | Retired interface paths kept for redirect. Issue #321: **"Preserve legacy code until dependency/rollback evidence allows removal."** |

## Not attempted — unverifiable in this environment

`ui/src/**` was scanned for zero-reference exports and **found several**
(for example `BoardServer` in `ui/src/fd/board-server.ts:44`, `isEdited`
in `ui/src/fd/edit-model.ts:17`, `MEMORY_SETTABLE` /
`MEMORY_TABLE_LABEL` / `tableLabel` in `ui/src/fd/api.ts`). **None were
removed.** The reason is a verification limit, not a judgement about the
code: this lane has no Node toolchain and no `ui/node_modules`, so the
interface test suites (`ui/src/test/*.test.tsx`, `ui/e2e-fd/*.spec.ts`)
could not be run. Retiring a unit whose only proof is "no consumer" while
being unable to run the suite that would catch a missed one is exactly the
trade this lane exists to avoid.

Two of those candidates also sit close to protected code —
`MEMORY_SETTABLE` / `MEMORY_CREATE_ALLOWED` are the Memory-store surface —
so they need the owner's call before any removal.

The same reason applies to the Python suite: see "Verification" below.

## Verification actually run

| Check | Command | Observed |
|---|---|---|
| Whole package still parses | `python3 -m compileall -q src` | `ALL SRC COMPILES OK` |
| Each touched module still parses | `python3 -m py_compile src/personal_world/{chat_registry,briefing,prefs,push}.py` | OK for all four |
| No retired name survives anywhere | `grep -rn "\bChatProviderRegistry\b\|\bknown_system\b\|\bdumps_place\b\|\bCONTRAST_FLOOR\b\|\bTEXT_SCALE_FLOOR\b\|\bDENSITY_FLOOR\b\|\bstatus_word\b" src tests scripts ui/src ui/e2e-fd ui/e2e` | zero hits |
| No retired name is re-imported | AST import graph over every `.py` in `src/`, `tests/`, `scripts/` | zero importers |
| No dynamic path can reach them | `grep -rn "importlib\|getmembers\|__subclasses__" src tests scripts` | only `worlds/db.py:118,122`, fixed module tuple |
| No test keeps them | `grep -rn "<name>" tests/` | zero hits for all seven |
| Doc links resolve (`tests/test_docs.py` rule) | markdown link/anchor check run over this file | all targets exist |

**Not run, and why:** `pytest` could not execute here. The clone has no
virtualenv, `pytest`, `fastapi`, or `pyyaml` installed, and the sandbox has
no network (`pip install` fails with a proxy 403), so
`uv run pytest` / `python3 -m pytest` cannot resolve the test extra. The
static proofs above stand on their own — a zero-consumer claim is a claim
about the import graph, not about runtime — but a maintainer with a working
environment should run `python3 -m pytest` before this branch lands. That is
recorded as an open item rather than papered over.

## Decisions in force

Quoted, not paraphrased, and not contradicted by any commit in this lane:

- 2026-10-13 Rylee: "Not yet. Wanna get it cleaned up first then we design."
  then "Ok do add the api and visuals. Hah" — cleanup runs first; design
  and contract run beside it.
- 2026-10-13 issue #321: "Preserve legacy code until dependency/rollback
  evidence allows removal."
- 2026-10-13 issue #319: "name live consumers and preservation tests before
  changes."
- 2026-10-13 Claude (desk), on the PR_LIMIT conflict: "s0-retire lands as
  ONE draft PR, one commit per retirement, each commit message carrying its
  consumer proof and rollback (git revert `<sha>`)."
- 2026-10-13 Claude (desk), same answer: protected code — auth, owner/CSRF,
  Memory store, art/canon, receipts, actions at-most-once — is Rylee's
  alone and needs a picker card first.

## Related

- [ORPHANS.md](../surfaces/ORPHANS.md) — the dated orphan index this lane's
  keep-list reconciles against.
- [REPOSITORY-INVENTORY.md](../repo/REPOSITORY-INVENTORY.md) — the earlier
  inventory pass that first flagged `execution_viewer` (ORPH-05) and the
  duplicate chat builders (ORPH-01/02).
- [MASTER-SURFACE-REGISTRY.md](../surfaces/MASTER-SURFACE-REGISTRY.md) and
  [PROVIDER-MATRIX.md](../surfaces/PROVIDER-MATRIX.md) — where `ChatProviderRegistry`
  was already recorded as `ORPHAN` / `NO (orphan)`, which is why removing it
  contradicted no existing decision.