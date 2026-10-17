# Plan: remove the old UI tree (mechanical)

Goal: delete the old Worlds UI that the front-door UI replaced. You do NOT write code yourself: workers do, via `offload`. Your job is to dispatch, verify, and report honestly.

## Tasks
| ID | What | Brief for the worker | Acceptance (run from the repo root AFTER you bring the worker's patch in) | Tier |
|---|---|---|---|---|
| T5 | git rm the listed old files, fix the Storybook preview and dangling refs | `docs/rebuild/foreman/briefs/T5.md` | `cd ui && npx tsc -b && npx oxlint && npx vitest run --project unit && npm run tokens:check` | `-m code` |
| T6 | Fix stale README / vite comment | `docs/rebuild/foreman/briefs/T6.md` | `cd ui && ! grep -n "e2e-api\|src/screens\|src/components" README.md vite.config.ts && npx tsc -b` | `-m code` |

T6 needs T5 committed first. Give workers both `briefs/COMMON.md` and their brief. If `ui/node_modules` is missing in your clone run `ln -s <the real checkout>/ui/node_modules ui/node_modules`.

## How to delegate
`offload agent -m code --repo . --brief docs/rebuild/foreman/briefs/T5.md --name t5 "Implement task T5 per the brief"` (likewise T6). Run the printed `--- apply:` command, then the acceptance command yourself; the acceptance run is the truth. Then verify the deletion is exactly the list: `git diff --name-status HEAD~1 HEAD -- ui | grep '^D' | wc -l` must equal the list length plus the 3 scripts/report files, and `git diff --name-only --diff-filter=ACMR HEAD~1 HEAD` may show only `ui/.storybook/preview.tsx` (T5) and `ui/README.md`, `ui/vite.config.ts` (T6) and package/tsconfig references the brief allowed. Commit accepted work per task (`git add -A -- ui && git commit`), never push.

## Budget and rules
- At most 3 worker runs. A retry needs a new brief quoting the failing output.
- At most 25 minutes.
- Never delete a file that is not in `docs/rebuild/foreman/old-ui-delete-list.txt` (except the 3 named in T5 step 3). Never edit or delete anything under `ui/src/fd/`, `ui/src/test/fd-*`, `ui/e2e-fd*`. If a test or the type check fails because of a deletion, stop that task and report; never edit a test to pass.
- Never deploy, push, or touch the network. You have no Edit/Write tools.

## Final report (your last message must END with this JSON on one line, nothing after it)
{"tasks": {"T5": "done|blocked|escalated", "T6": "done|blocked|escalated"}, "worker_runs": <int>, "acceptance_pass": {"T5": true|false, "T6": true|false}, "deleted_count": <int>, "escalations": ["short reason"]}
Before it, write 3-5 plain sentences: what is verified, what is not, and anything the owner must decide.
