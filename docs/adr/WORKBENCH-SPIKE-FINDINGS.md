# Workbench spike findings (Lane W, backend only)

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (evidence for `docs/adr/0003` and `docs/adr/0006`) · **Read this if:** you want to see what a spike actually found when the Workbench ADRs met the code. · **Superseded by:** `docs/adr/0003-workbench-core-owned-capability.md` and `docs/adr/0006-event-task-envelope.md`

**In short:** a dated record (2026-09-21) of what fit and what did not when the Workbench and task-envelope ADRs were tried against the code. It is evidence, not current state — both ADRs remain **proposed**, and the test counts and commit hashes are that session's.

- Date: 2026-09-21 · Branch `lane/workbench-spike` off main @ `58f3b5e`
- Proves ADR-0003 (core-owned workbench capability) and ADR-0006
  (task/event envelope on the journal) against the code as it actually
  is. Status of those ADRs is unchanged: **proposed, review-only**.
- Evidence: `tests/test_workbench_spike.py` (29 tests), full suite
  `1229 passed, 7 skipped`, `personal-world framework validate` → 0 violations.
- Surface touched: `providers/workbench.py` (new), `model.py` (+20
  additive), `app.py` (+26 wiring), `test_framework.py` (+1 capability
  name). **`api.py`: zero changes** — registration through
  `build_registry` needs no routes (reported below).

## What the ADRs assumed vs what the code allows

| ADR claim | Spike verdict |
|---|---|
| 0003-1 "workbench/terminal/task/preview are core-owned capabilities a provider implements" | **Fits as-is.** `Registry.define_capability` + one `registry.register` call is the whole seam. Capability name `workbench`, provider `workbench-podman`, mode ENRICHMENT — exactly the ADR-0001 shape, no new machinery. |
| 0003-2 "native baseline = honest not_configured, zero-provider boot" | **Fits, one nuance.** The registry answers `not_configured` for an unregistered capability — that IS the honest off-state. So the gate lives at *registration* (`PW_WORKBENCH=1`), not inside `observe()`. The Traefik env-gate precedent (`PW_TRAEFIK_BASE_URL`) already does this; the spike follows it. `Status.DISABLED` exists in the enum but no capability path renders it, and `test_framework`'s zero-provider gate *requires* `not_configured`. |
| 0003-4 "terminal/exec go through a capability-scoped broker… never arbitrary host shell" | **Implementable today, but only as provider convention.** The spike IS the broker: argv-list-only, regex-checked container names, empty env, timeout, no mount flags, refusal-by-default allowlist. There is no framework-level broker between a route and a provider `impl` — nothing stops a future provider calling `subprocess(shell=True)`. The "broker boundary contract" ADR-0003 itself forecasts is still unwritten; this file is evidence for what it must mandate. |
| 0006-1 "one envelope: event_id · timestamp · source · subject/type · task_id · state · payload · correlation_id" | **Fits the journal with an additive change, not zero change.** `JournalEvent` had ts/kind/provenance.source (timestamp/subject/source) but NO event_id/task_id/state/payload/correlation_id. Pydantic silently ignores extra kwargs — the first naive attempt would have *dropped the task fields while appearing to work*. The spike adds 5 optional fields + `JournalKind.TASK`, same pattern the supersede block used. Pre-existing rows still validate. |
| 0006-2 "the envelope is a journal event shape, not a new bus or store" | **Held.** One `journal.append(JournalEvent(kind=TASK,…))` per execution; no new storage. NOTE: `execution_viewer.py` already exists as a *second* execution-record store (`executions.json`) with its own id/status/stdout fields. The code allows both; the ADR says journal is home. Convergence is an owner call (below). |
| 0006-5 "Task = unit of executing work (inputs · status · logs · workspace-or-node · artifacts · events)" | **Partially expressible.** inputs(argv)/status(state)/logs(tail)/workspace(container) map onto `payload`. **artifacts have no home** — the envelope carries none, and inventing one is out of spike scope. |

## Honest gaps found while wiring (none fatal)

1. **Registry health-check masking.** `Registry.observe()` short-circuits
   a failing health check into a generic `unavailable` *before* the
   provider speaks — the specific `unavailable: podman not found` reason
   would be lost. The spike registers `health_check=lambda: True`
   (Traefik precedent) so all status lives in honest `observe()`.
   Consequence: `/api/actors` will list `workbench-podman` as healthy
   even when podman is missing. A real fix is a registry that renders
   the provider's own degraded Result into Actor status — out of scope,
   flagged.
2. **Rootless podman wants a client env.** "Explicit empty env" is
   proven and right for the *exec'd task*, but `shutil.which` +
   `env={}` for the *podman client* itself will break rootless podman
   (it needs `XDG_RUNTIME_DIR`, often `HOME`). On this Bazzite host
   distrobox runs rootless, so a live demo must either use `--rm`-free
   system podman or pass a curated client env. The spike's config seam
   is `podman_env` (explicit allowlist, never inheritance). This is the
   same decision as "empty env vs curated env" below.
3. **Timeout kills the client, not the in-container process.**
   `subprocess.run(timeout=…)` SIGKILLs `podman exec`; the process the
   task started *inside* the container keeps running (visible as a
   still-exec'd process next `ps`). Durable kill needs either
   `podman exec` + a container-side `timeout` wrapper or a follow-up
   `podman kill` policy. Recorded as `state=timeout`, honestly labeled,
   not solved.
4. **`cli.py status/manifest` omits journal/vault/data_dir when building
   the registry** (a divergence `docs/repo/WIRING-READINESS.md` already
   records). Consequence: `run_task` via that path refuses —
   "no journal wired: run_task refuses to execute unaudited work".
   Fail-closed working as designed; `cli_dispatch` passes the journal
   and is fine.
5. **Every journal row now serializes 5 new `null` fields.** Readers are
   unaffected (append-only rows validate unchanged); writers get
   slightly fatter lines. Acceptable for the spike; if owners want a
   frozen core row shape, the alternative is a typed submodel
   (`envelope: TaskEnvelope | None`) — one-field diff either way.
6. **No attach, no streaming, no routes, by scope.** `run_task` is
   synchronous; a long task blocks its request until timeout. ADR-0006's
   WebSocket transport therefore has *nothing to push yet* — the journal
   row is written at completion, not at start. Streaming needs a
   start-event + an incremental sink; that is exactly the durable-broker
   trigger ADR-0006-4 names, so demo attach decisions below should be
   made knowing the journal envelope is completion-only as built.

## api.py: the exact registry-required diff (report)

**None.** `create_app` builds the registry per request through
`build_registry` and surfaces it via `/api/status` (status_map),
`/api/manifest`, `/api/actors`. Defining the capability
(`STANDARD_CAPABILITIES += ("workbench", …)`) and registering the
provider inside `app.py` makes it appear on all three with zero api.py
edits. `test_framework.py` gained one line (`"workbench"` in its
exact-set assertion). The morning demo drives the provider object
directly (below); a route would be the *next* commit, made with the
auth story deliberate (an exec endpoint needs the step-up gate, not the
plain bearer gate — `require_step_up` is the precedent at
`/api/journal/supersede`).

## The three decisions the owner makes in the morning

1. **Attach mechanism.** Demo options: (a) keep `run_task` synchronous
   argv-in/argv-out (what is built and tested; 10-line demo below);
   (b) add a *start-event at launch* to the envelope (state=`started`)
   so a WebSocket can list live tasks — cheap in code, but crosses the
   ADR-0006-4 "durable/streams" trigger: decide knowingly; (c) real TTY
   attach (`podman attach`/exec-stream) — needs streaming storage the
   journal was not designed for. Recommended: demo (a) tonight, decide
   (b) vs (c) as the broker-contract's first clause.
2. **Default allowlist.** The spike fails closed (empty = deny
   everything), proven by tests. That is a *sane default* but a dead-on-
   arrival demo config. What should `PW_WORKBENCH_CONTAINERS` /
   connections.json `workbench.allowed_containers` default to on THIS
   machine — `ai-distrobox` only? Who may edit it (it is an
   authorization decision, so treat like `require_step_up` config, not
   free UI input)? Also: per-container argv constraints
   (command allowlists) — broker-contract material, absent today.
3. **Envelope fit.** Approve the 5 additive optional fields +
   `JournalKind.TASK` as the ADR-0006 landing shape (spike's choice,
   precedent-following) — or ask for a nested `TaskEnvelope` submodel,
   and separately: does `ExecutionViewer` fold into the journal (one
   store, per ADR-0006-2) or stay the executions view it is (two stores
   already)? Unfreezing `payload` keys (artifacts, workdir,
   started/finished) is part of this decision too.

## 10-line how-to-demo (owner session)

```python
from personal_world.providers.workbench import WorkbenchPodman
from personal_world.journal import Journal
import os
os.environ["PW_WORKBENCH"] = "1"          # the enable switch
wb = WorkbenchPodman(                      # stand up one directly
    config={"allowed_containers": ["ai-distrobox"],
            "podman_env": {}},             # (rootless: maybe needs XDG_RUNTIME_DIR)
    journal=Journal("data/journal.ndjson"))
print(wb.observe().status)                 # healthy / unavailable: reason
print(wb.list_environments().data)         # the REAL distrobox list
r = wb.run_task("ai-distrobox", ["uname", "-a"])   # argv list, never a shell
print(r.ok, r.data["stdout"], r.data["task_id"])   # journal row written: kind=task
```

…then: `tail -1 data/journal.ndjson` shows the envelope fields
(`event_id`, `task_id`, `state`, `payload`, `correlation_id`) the ADR
promised and the spike proved.

## What this spike refuses

UI, attach/streaming, network exposure, api.py routes, host shell,
volume mounts, env inheritance, auto-registering any container, NATS or
any new service, and merging to main. None of it is needed for the
thin slice; all of it is the RMM drift the ADRs warn about.
