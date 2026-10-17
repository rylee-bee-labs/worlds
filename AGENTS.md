# AGENTS.md

Before substantive work, read [`AGENT_POLICY.md`](AGENT_POLICY.md) and
[`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md), then load only the contracts
that apply.

**What the repository shows beats what you infer. UNKNOWN is valid.**

## Worlds in one paragraph

Worlds is a public, self-hosted personal front door.

Repository: `personal-world`  
Package: `personal_world`  
Environment prefix: `PW_`

Current architecture is [ADR-0008](docs/adr/0008-front-door.md):

```text
Home · Connect · Memory · Settings
```

Worlds owns meaning. Providers own mechanics.

## What owns what

- **Home** composes useful cards and attention.
- **Connect** describes providers, mappings and requests in files.
- **Memory** keeps durable personal state, deterministic local search,
  history, export and restore.
- **Settings** holds configuration and comfort.
- **Companion** is presentation/conversation around the product, not a second
  authority path.
- External `room/0` systems continue as a provider kind. Worlds calls them
  services and does not absorb their implementation.

Provider API shapes do not become Worlds concepts.

## Authority

Consequential actions use one governed path:

```text
request
→ approve
→ durably consume authorization
→ dispatch at most once
→ SUCCEEDED | FAILED | UNKNOWN
```

A retry is a new action. Project Home stays canonical for operations it
governs; other provider actions stay explicitly owner-authorized through
Worlds' own boundary.

## Memory baseline

The rebuild treats Memory as durable product state from day one, and supports:

- Kept
- Later
- Records
- History
- Find

Local deterministic search works with providers and models off.
Backup/restore is a current front-door path, not the retired old-app bundle
format. See [`docs/rebuild/DURABILITY.md`](docs/rebuild/DURABILITY.md).

## Branches

`main` is the active line, and it **is** the front-door application: the
`rebuild/front-door` line was merged into `main` in PR #277 (2026-10-06).
That was a *source* cutover — merging publishes an image, it does not
deploy; deploying the front door is a separate, deliberate owner step
(`.project/CURRENT.md`).

Older documents that describe `main` as "pre-front-door", or that treat
`rebuild/front-door` as the live lane, are drifted history. Keep their
content; do not read their branch claims as current.

If a `rebuild/front-door` remote branch still exists, derive divergence
before assuming anything about it:

```sh
git fetch origin
git rev-list --left-right --count origin/main...origin/rebuild/front-door
```

Current work belongs in GitHub Issues. See `.project/CURRENT.md`.

## Map

| Path | Owns |
| --- | --- |
| `src/personal_world/` | Python application/runtime |
| `tests/` | backend + public-safety verification |
| `ui/` | browser interface |
| `config/` | public/synthetic configuration and recipes |
| `.project/CURRENT.md` | current-state routing |
| `.project/PLAN.md` | product direction |
| `.project/DECISIONS.md`, `docs/adr/` | durable decisions |
| `.project/contracts/adoption.yaml` | Play-Nice adoption pin |
| `docs/` | contracts, architecture, operations and history |
| `docs/vnext/docs-truth.md` | which file owns each command/claim, and which docs are superseded |
| `design/` | deliberate design/art sources |
| `.agents/skills/` | repo-local task skills |

Generated output stays generated. Do not hand-edit generated token/API/build
artifacts when their owning generator exists.

## Checks

Use the branch's checked-in workflows as the authority. Common gates are:

```sh
uv sync --frozen --extra test --extra crypto
uv run pytest --timeout=30
uv run personal-world framework validate --json
uv run python scripts/contract-drift-check.py   # routes/spec vs. the live app

cd ui
npm ci
npx tsc -b
npm run lint
npx vitest run
npm run build
npx playwright test
```

Run the relevant subset locally and let GitHub CI run the repository's full
required set.

A green source check is not runtime verification.

**Generated inventories, not hand copies.** Routes, the OpenAPI document
and the token set are generated; if a route or a spec shape moved, run
`uv run python scripts/gen-openapi.py` and
`uv run python scripts/contract-drift-check.py --write` and review the
diff instead of editing `ui/src/generated/` or restating an endpoint list
in a Markdown page. [`docs/vnext/docs-truth.md`](docs/vnext/docs-truth.md)
names the owner of each command and claim.

## Work discipline

- Use a topic branch/worktree for bounded work.
- Parallel lanes use separate worktrees.
- Never `git add -A` across shared/concurrent work.
- Stage explicit paths.
- One issue owns durable unfinished work when the work must survive a session.
- One PR is the integration/evidence packet for a coherent slice.
- Do not manufacture a dated handoff as routine session ceremony.

Dated `.project/HANDOFF-*` files are history/evidence. They do not outrank
current code, issues, ADRs or `.project/CURRENT.md`.

## Checkouts and paths

`personal-world` is worked in from more than one checkout: this repository has
linked worktrees in use, and the estate also holds in-root checkouts of it. A
worktree is a checkout of this repository, not a separate repository, and a
repository is not a worktree.

Before writing or checking any path, run from the repository root:

```sh
git worktree list
```

Every relative path in a document must resolve from the repository root. A
path that only resolves from inside a worktree or a sibling directory is
wrong. If a `cd` destination is written down, it must be right for someone
who just cloned the repository and nothing else.

## Sources of truth

- Current routing: `.project/CURRENT.md`
- Direction: `.project/PLAN.md`
- Front-door architecture: `docs/adr/0008-front-door.md`
- Which doc owns which command or claim: `docs/vnext/docs-truth.md`
- Routes/API surface (generated): `scripts/route-inventory.json`, `ui/src/generated/openapi.json`
- Browser interface: `FRONTEND-INVENTORY.md`
- Security/public boundary: `SECURITY.md`
- Accessibility: `docs/accessibility/ACCESSIBILITY_CONTRACT.md`
- Human reliability: `docs/HUMAN_RELIABILITY_CONTRACT.md`
- Play-Nice: `.project/contracts/adoption.yaml`
- Decisions: `.project/DECISIONS.md` + `docs/adr/`
- Work queue: GitHub Issues
- Live runtime: the running app's revision evidence, never prose

Older TRUE-NORTH, product-language, finish-line, roadmap and handoff documents
are useful history/idea sources where not explicitly preserved by current
decisions. ADR-0008 wins on front-door structure.

## Front-door rules

- Landmarks are `Home · Connect · Memory · Settings`.
- Configuration is files and must round-trip without a hidden UI-only canon.
- Memory has a deterministic local baseline and understandable export/restore.
- Consequential actions use one explicit authority path.
- A saved request is not automatically an agent tool.
- Dispatch is at-most-once per consumed authorization; retry is a new action.
- Project Home remains canonical for operations it governs.
- Themes/Station/character packs may change presentation and voice, not
  structure or accessibility floors.
- External `room/0` systems remain supported as a provider kind. Worlds code
  calls them services; do not rebuild their mechanics inside Worlds.

## External mechanics / Workbench boundary

These rules remain binding even though older Workbench/Node product plans are
not current front-door navigation:

- Prefer documented APIs/CLIs/open protocols over embedding another product's
  UI.
- No core capability may depend on an Enterprise-only feature.
- Foundational dependencies need a usable self-hosted open-source path.
- Copyleft services stay behind a clean external-service boundary.
- Do not create duplicate identity, secrets, networking, storage, build or
  remote-access infrastructure when the estate already owns it.
- Valuable state is explicit; containers are replaceable.
- Any terminal/exec capability must be capability-scoped and confined. Never
  expose a raw container socket or arbitrary host shell as routine mechanics.
- Remote failures are visible `unavailable`/`stale`, not hidden.

## Public repository boundary

This repo is public.

Never commit:

- credentials or tokens,
- secret values,
- private addresses/topology,
- personal journals/memory,
- private provider payloads,
- runtime logs containing private data.

Use synthetic/reserved examples. `tests/test_public_safety.py` is the
regression gate.

## Cross-repo boundary

Do not silently mutate sibling repositories as part of Worlds work.

When another repo owns a required change, use or create its issue/work packet.
Worlds should carry only the interface/boundary it owns.

## Owner gates

Explicit owner approval is required for:

- production cutover/deploy,
- real secrets/tokens,
- production data mutation/deletion,
- destructive remote-branch/data removal,
- deliberate artwork/source-rig replacement,
- contract re-pinning outside the normal pin workflow when policy requires
  review.

## Done

Substantial work ends with the report shape from `AGENT_POLICY.md`:

- **CHANGED**
- **VERIFIED**
- **CONTRACTS**
- **ACCESSIBILITY**
- **OWNERSHIP/SECURITY**
- **UNKNOWN**
- **DEFERRED**
- **NEXT**

Keep source-ready, merged, published, deployed and runtime-verified as distinct
states.
