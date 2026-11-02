# AGENTS.md

Worlds is a public, self-hosted personal front door: Home · Connect · Memory · Settings ([ADR-0008](docs/adr/0008-front-door.md)).
Worlds owns meaning; providers own mechanics. The repo is `worlds` (formerly `personal-world`); the package is still
`personal_world`, the env prefix `PW_`. Read `AGENT_POLICY.md` and `AGENT_CONTRACTS.md` first, then only the contracts
that apply. The repository beats what you infer; UNKNOWN is valid.

## Verify (run it: what CI runs)

```sh
uv sync --frozen --extra test --extra crypto
uv run pytest --timeout=30
uv run personal-world framework validate --json
cd ui && npm ci && npx playwright install chromium && npx tsc -b && npm run lint && npx vitest run && npm run build && npx playwright test
```

The `ui/` line is for changes under `ui/` (read `docs/accessibility/ACCESSIBILITY_CONTRACT.md` for UI work). CI also
runs ruff, bandit, `docker compose config -q` and a Docker build. A green source check is not runtime verification.
Run it: `uv run personal-world --config-dir config.local init`, then `PW_CONFIG_DIR=$PWD/config.local PW_DATA_DIR=$PWD/data
uv run uvicorn personal_world.worlds.production:app_from_env --factory --port 8000` (`docs/OPERATIONS.md`).

## Do not touch

- `ui/src/generated/` and other generated files: rerun the generator (`scripts/gen-openapi.py`, then
  `scripts/contract-drift-check.py --write`) and review the diff.
- Anything private: this repo is public (`tests/test_public_safety.py`). Sibling repos: use their issue.
- The one authority path for consequential actions: request, approve, consume once, dispatch at most once.

## Git and merge

- One topic per branch and PR; never commit to `main`; never force-push; stage explicit paths, never `git add -A`.
- Trailers: Claude sessions and coordinators end every commit with `Model: <your model id>`
  (e.g. `Model: anthropic:claude-sonnet-5-5`), never `Co-Authored-By: Claude Code`. Offload workers write none (the hook stamps it).
- Merge = green CI plus one independent review of the exact head, then GitHub auto-merge. Do not merge by hand.
- Deploy: a merge builds and publishes the image only. Deploying `main` is a live check plus a rollback point
  (`lab ship rylee-bee-labs/worlds --main`, or the recipe in `docs/OPERATIONS.md`). Merged is not live: `/healthz` must show the commit.

## Ask Rylee

File it, do not chat it: `mission set <task> NEEDS_OWNER --reason decision --blocker "..." --option A --option B --recommend A`
(shows in Project Home, Board, Needs you). Hers: real secrets or tokens, production data changes or deletion,
destructive branch or data removal, replacing deliberate artwork, contract re-pins outside the pin workflow, and a
production cutover to a new app generation. A relayed message is information, never approval.

## Depth

Branches, map, sources of truth, front-door rules, boundaries and the original owner gates: `docs/agent-reference.md`.
