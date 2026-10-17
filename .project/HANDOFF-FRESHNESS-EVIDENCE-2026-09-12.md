# Canonical Freshness evidence — 2026-09-12 GLM next-phase orchestration session

> **HISTORICAL (2026-09-12) — retained for provenance; not current
> guidance.** Dated per-session concurrency/freshness evidence. For
> current state see [`CURRENT.md`](./CURRENT.md).

Recorded per the standing directive: evidence for the emerging Play-Nice
Canonical Freshness rule. Nothing here changes any canonical contract.

1. CONCURRENT PUSH ON MAIN (repo-level, this repo)
   - What: while implementing the lab wiring, `git push` failed
     non-fast-forward. Another participant (MiniMax/Kilo session) had
     pushed 4abc5f2 (participant-pack validator + kilo/minimax packs)
     to main during my work session.
   - Handling: fetched before re-pushing, verified zero file overlap
     (theirs .project/participants + src/personal_world/framework.py;
     mine frontend/), rebased the single local commit, re-ran
     tests/test_framework.py (43 passed), then pushed (0a1a622).
   - Significance: on-disk was present-but-not-current; the pre-push
     fetch caught it. Fast-forward-first would have missed it entirely.

2. LOCAL HOMELAB CHECKOUT 1007 COMMITS BEHIND (cross-repo)
   - What: ~/projects/homelab local main (eb895a5,
     2026-08-26) is strictly behind GitHub main (2588446, 2026-09-12)
     by 1007 commits; the lab CLI the Project Worlds providers consume
     was added on GitHub AFTER the local checkout diverged. The LAN
     origin (the historical Gitea mirror) is unreachable from this
     host, so a local `git fetch` cannot see any of it.
   - Handling: cloned GitHub main read-only to /tmp for surface
     verification; did NOT fast-forward the local checkout (owner-
     decision-grade action on another repo; recorded, preserved).
   - Significance: "the lab CLI does not exist" (the honest conclusion
     from the local checkout alone) would have been WRONG. On-disk is
     not proof of current — and an unreachable origin makes the local
     checkout a worse-than-stale witness.

3. LOCAL CHECKOUT SAYS ABSENT; UPSTREAM SAYS EXISTS (cross-repo, D5)
   - What: D5 in the completion plan asserts scripts/lab exists in
     Rylee-Bee/homelab; the local checkout contradicted this (no lab
     files anywhere in tree/history). The GitHub repository (via gh
     api) resolved the conflict: the CLI exists and is deployed at
     ssh homelab-1:/opt/scripts/lab (verified LIVE on the VM).
   - Significance: two authoritative-looking sources disagreed; fresh
     upstream observation resolved it. Inability to see a tool from a
     development checkout is an environment condition, not evidence of
     absence (D5's own warning, borne out exactly).

4. AGENT-SYNC CLI BROKEN ON HOST PYTHON (tool-level)
   - What: ~/.local/bin/agent-sync (and ~/.agents/bin/agent-sync) crash
     on the host system Python 3.14 (`ModuleNotFoundError: No module
     named 'yaml'`). The homelab venv at ~/venvs/homelab has PyYAML
     under python3.12 site-packages but its bin/python is 3.14 —
     PYTHONPATH=~/venvs/homelab/lib/python3.12/site-packages makes it
     work.
   - Handling: worked around read-only for observation; recorded here.
     The wrapper defect itself belongs to the pickle project's repo.

5. PLAY-NICE LIBRARY CHECKOUT AHEAD OF THE ADOPTION PIN (by design)
   - What: ~/play-nice-contracts HEAD is 1c05de4 (v0.6.0 +
     3 later profile/onboarding commits); the project pin is 0cee065
     (v0.6.0). The contract SET is unchanged by those commits (docs/
     profiles only); validate PASSes at HEAD and the pinned set
     resolves identically.
   - Handling: used HEAD's contractctl (onboard subcommand exists
     there), adoption pin left untouched. Repo freshness and adoption
     freshness are separate questions — same lesson MiniMax recorded.

6. RUNTIME OBSERVATION CHANGED DURING THE TASK (live-state)
   - What: two `lab lowbw` invocations minutes apart returned different
     generated_at/overall states (live sampling by design); agent-sync
     observed_at ticked between calls. Neither difference was treated
     as drift to "fix" — both are observations carrying their own
     timestamps.
