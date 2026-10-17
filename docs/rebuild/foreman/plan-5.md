# Plan: L-recipes content (sanitized service recipes)

Goal: draft the recipe files and sample responses for the homelab services. You do NOT write files yourself: workers do, via `offload`. Your job is to dispatch, verify, and report honestly.

## Tasks
| ID | What | Brief for the worker | Acceptance (run from the repo root AFTER you bring the worker's patch in) | Tier |
|---|---|---|---|---|
| T7 | sonarr, radarr, lidarr, prowlarr | `docs/rebuild/foreman/briefs/T7.md` | `PYTHONPATH=src ~/code/Rylee-Bee/personal-world/.venv/bin/python -m pytest tests/recipes -q -k "sonarr or radarr or lidarr or prowlarr"` | `-m code` |
| T8 | bindery, bazarr, cleanuparr, houndarr | `docs/rebuild/foreman/briefs/T8.md` | `... -k "bindery or bazarr or cleanuparr or houndarr"` | `-m code` |
| T9 | gatus, settings-drift, authelia, traefik | `docs/rebuild/foreman/briefs/T9.md` | `... -k "gatus or settings-drift or authelia or traefik"` | `-m code` |
| T10 | planned: qbittorrent, grimmory | `docs/rebuild/foreman/briefs/T10.md` | `... -k "qbittorrent or grimmory or planned"` | `-m code` |

The four tasks are independent. Give every worker `docs/rebuild/foreman/briefs/COMMON-R.md` and its own brief. Workers need no network. The Python venv is the one named in the acceptance command; do not create another.

## How to delegate
`offload agent -m code --repo . --brief docs/rebuild/foreman/briefs/T7.md --name t7 "Implement task T7 per the brief"` (likewise T8, T9, T10; run them one after another, not in parallel). Run the printed `--- apply:` command, then the task's acceptance command yourself; the acceptance run is the truth. Then run the whole `tests/recipes` directory once. Commit accepted work per task (`git add config/recipes tests/recipes/samples && git commit`), never push.

## Budget and rules
- At most 6 worker runs. A retry needs a new brief quoting the failing output.
- At most 40 minutes.
- Only files under `config/recipes/` and `tests/recipes/samples/` may change. Never edit `tests/recipes/test_recipes.py`, `tests/recipes/test_recipes_module.py` or anything under `src/`. If a check looks wrong or contradicts a brief, stop that task and report; never work around it.
- Nothing private: no real hostname, domain, IP, tracker, topic or personal name in any file. If a worker adds one, reject the patch.
- Never deploy, push, or touch the network. You have no Edit/Write tools.

## Final report (your last message must END with this JSON on one line, nothing after it)
{"tasks": {"T7": "done|blocked|escalated", "T8": "...", "T9": "...", "T10": "..."}, "worker_runs": <int>, "acceptance_pass": {"T7": true|false, "T8": true|false, "T9": true|false, "T10": true|false}, "escalations": ["short reason"]}
Before it, write 3-6 plain sentences: what is verified, what is not, and anything the owner must decide.
