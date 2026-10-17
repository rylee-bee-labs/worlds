# Plan: L-experience slice 1 (shell, row, Home skeleton)

Goal: build the new Worlds front-door shell and Home against fixtures. You do NOT write code yourself: workers do, via `offload`. Your job is to dispatch, verify, and report honestly.

## Tasks
| ID | What | Brief for the worker | Acceptance (run from the repo root AFTER you bring the worker's patch in) | Tier |
|---|---|---|---|---|
| T1 | Shell + landmarks | `docs/rebuild/foreman/briefs/T1.md` | `cd ui && npx vitest run --project unit src/test/fd-shell.test.tsx` | `-m code` |
| T2 | Meter + Row | `docs/rebuild/foreman/briefs/T2.md` | `cd ui && npx vitest run --project unit src/test/fd-row.test.tsx` | `-m code` |
| T3 | Strip + Home | `docs/rebuild/foreman/briefs/T3.md` | `cd ui && npx vitest run --project unit src/test/fd-home.test.tsx` | `-m code` |

Every brief also follows `docs/rebuild/foreman/briefs/COMMON.md`; give workers both. T1 and T2 are independent. T3 needs T2 committed first.
Run `ln -s <the real checkout>/ui/node_modules ui/node_modules` first if `ui/node_modules` is missing in your clone (workers cannot install packages). The real checkout path is the repo path you were launched with.

## How to delegate
`offload agent -m code --repo . --brief docs/rebuild/foreman/briefs/T1.md --name t1 "Implement task T1 per the brief"` (and likewise T2, T3). Run the printed `--- apply:` command, then the task's acceptance command yourself; the acceptance run is the truth. Commit accepted work locally per task (`git add <named paths> && git commit`), never push.

## Budget and rules
- At most 6 worker runs in total (retries count). A retry needs a new brief quoting the failing output.
- At most 40 minutes wall clock.
- Never edit, delete or weaken `ui/src/test/fd-*`, or `ui/src/fd/{types,fixtures,msw,api,route,prefs,home-model}.ts(x)`. If a test looks wrong or contradicts a brief, stop that task and report the conflict; never work around it.
- Never deploy, push, or touch the network. You have no Edit/Write tools. If a worker fails twice on a task, mark it blocked and move on.
- Only files under `ui/src/fd/` may change (plus nothing else).

## Final report (your last message must END with this JSON on one line, nothing after it)
{"tasks": {"T1": "done|blocked|escalated", "T2": "...", "T3": "..."}, "worker_runs": <int>, "acceptance_pass": {"T1": true|false, "T2": true|false, "T3": true|false}, "escalations": ["short reason"]}
Before it, write 3-6 plain sentences: what is verified, what is not, and anything the owner must decide.
