# Plan: L-experience slice 2 (Connect, Memory and Settings skeletons)

Goal: build three skeleton screens. You do NOT write code yourself: workers do, via `offload`. Your job is to dispatch, verify, and report honestly.

## Tasks
| ID | What | Brief for the worker | Acceptance (run from the repo root AFTER you bring the worker's patch in) | Tier |
|---|---|---|---|---|
| T4 | Connect, Memory, Settings | `docs/rebuild/foreman/briefs/T4.md` | `cd ui && npx vitest run --project unit src/test/fd-screens.test.tsx` | `-m code` |

Give the worker both `docs/rebuild/foreman/briefs/COMMON.md` and the T4 brief (the T4 brief tells it to read COMMON). Run `ln -s <the real checkout>/ui/node_modules ui/node_modules` first if `ui/node_modules` is missing in your clone.

## How to delegate
`offload agent -m code --repo . --brief docs/rebuild/foreman/briefs/T4.md --name t4 "Implement task T4 per the brief"`. Run the printed `--- apply:` command, then the acceptance command yourself; the acceptance run is the truth. Commit accepted work (`git add <named paths> && git commit`), never push.

## Budget and rules
- At most 3 worker runs. A retry needs a new brief quoting the failing output.
- At most 30 minutes wall clock.
- Never edit, delete or weaken `ui/src/test/fd-*`, or `ui/src/fd/{types,fixtures,msw,api,route,prefs,home-model,Tabs}.ts(x)`, Home, Row, Meter, Strip, Shell. If a test contradicts a brief, stop and report; never work around it.
- Never deploy, push, or touch the network. You have no Edit/Write tools. Only files under `ui/src/fd/` may change.

## Final report (your last message must END with this JSON on one line, nothing after it)
{"tasks": {"T4": "done|blocked|escalated"}, "worker_runs": <int>, "acceptance_pass": {"T4": true|false}, "escalations": ["short reason"]}
Before it, write 3-5 plain sentences: what is verified, what is not, and anything the owner must decide.
