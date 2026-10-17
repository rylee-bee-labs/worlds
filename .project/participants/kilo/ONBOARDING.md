# Kilo Onboarding — Project Worlds

This is a fast orientation layer for any Kilo session landing on
Project Worlds. It is NOT a contract. It is the next agent's first
60 seconds.

## Who am I?

> You are operating through **Kilo** — an agent harness / CLI+TUI
> (opencode fork). Your brain/model may vary per session. Capability and
> authorization are NOT the same thing: Kilo exposes tools; the project
> authorizes their use.

The Kilo harness layer is profiled at `.project/participants/kilo/`.
The currently-loaded brain's profile (if any) lives at
`.project/participants/<brain-id>/`.

## Where am I?

- **Product name:** Project Worlds (renamed from "Personal World"
  2026-09-12 — product identity only).
- **Repository slug:** `Rylee-Bee/personal-world` (unchanged).
- **Working directory:** this repo's root.
- **Canonical current state:** `.project/CURRENT.md`.
- **Trunk:** `main` (one canonical trunk; the 2026-09-12 trunk-unification
  pass is complete).

## What do I read first?

In this order, stop when you have enough to act:

0. **Establish canonical freshness** — on-disk state is evidence of
   what is present, not proof of what is current. Before trusting any
   `.project/CURRENT.md` content as authoritative, run:

   ```bash
   git status --short
   git fetch origin
   git rev-list --left-right --count HEAD...origin/main
   git rev-parse origin/main
   ```

   If the local checkout is behind, fast-forward with
   `git pull --ff-only origin main` (do NOT merge or rebase without
   owner confirmation). Record the SHA you actually work against.
   **Repo freshness and Play-Nice adoption freshness are separate
   questions.** The repo should generally use current canonical project
   truth when safe; the adoption pin is whatever the project
   explicitly adopted and stays pinned unless the owner asks for a
   bump.

   **Escape hatch — canonical upstream unreachable.** If `git fetch`
   fails (offline, credential expired, network partitioned), do NOT
   pretend the local checkout is current. Record the observed local
   SHA, the timestamp of the failed fetch, and treat any work in this
   session as `PROVISIONAL` until freshness can be re-verified. The
   validator `personal-world framework validate-packs` still runs
   locally; only the cross-check against canonical upstream is
   deferred.

1. This file (you're reading it).
2. `.project/README.md` — the three-layer model (Play-Nice contracts →
   project context → participant packs).
3. `.project/CURRENT.md` — current product state.
4. `.project/contracts/adoption.yaml` — what is adopted at which
   revision. **Do not change the pin** unless the owner explicitly
   asks and you have verified the upstream commit + lockfile.
5. `.project/participants/README.md` — current pack table.
6. Only the task-relevant participant pack(s). Don't bulk-read all
   packs if the task doesn't touch them.
7. `AGENTS.md` and the project's `AGENT_CONTRACTS.md` for top-level
   operating rules.
8. Memory layer:
   - `memory_journal_check` if you suspect a prior failed attempt.
   - `memory_memory_search` if the task recurs across sessions.
   - `preferences_get_profile` for owner preferences not in the
     always-loaded files.

## What can Kilo do?

See `.project/participants/kilo/capabilities.yaml`. Short version:

- Read, search, edit, write files in the worktree.
- Run shell commands (read-only freely; mutating git commands prompt
  per command; confirmation cannot be saved as always-allow).
- Web fetch + search + several MCPs (memory, preferences, synology,
  proxmox, unifi, dns-traefik, gitea read-side, firecrawl, reddit,
  context7, figma, kilo-local-recall, inbox).
- Compose tool calls in structured form (tables, code fences,
  question tool, plan tool).
- NOT push, NOT merge, NOT deploy, NOT bypass confirmation, NOT
  rewrite another participant's pack without consent.

## What can the current brain do?

Read `.project/participants/<brain-id>/participant.yaml`. Do not
duplicate the brain's capability claims here — that file is the
authoritative source. If no brain pack exists, the brain is
unprofiled; record its capabilities via observation only, not
fabrication.

## Where does authority come from?

Order of authority (highest wins):

1. Live runtime state and what is actually on disk.
2. Source code / repo-tracked configuration.
3. Tests and validation (`uv run pytest`, `framework validate`).
4. Git history.
5. `.project/CURRENT.md` and the project canonical contracts.
6. `.agent/STATE.md` / `.agent/HANDOFF.md` (overwrite, keep concise).
7. `.agent/decisions/` (durable decisions).
8. Project `AGENTS.md` + `AGENT_CONTRACTS.md`.
9. Participant packs (enrichment, never canonical unless the project
   explicitly promotes information from them).
10. Semantic memory / lore (evidence about the past, never authoritative
    about present state).

**Authority is NOT:**

- The presence of a tool in the harness.
- A model reputation claim.
- A previous session's narrative summary.
- The brain's self-rating.

## When do I ask for help?

Use the `question` tool with 2-3 options (recommended option first)
when:

- Scope is ambiguous or the task could expand.
- Two valid architectures both work and the trade-off matters.
- Authority is unclear (especially across participant packs).
- You'd otherwise invent a value to complete a tidy summary.
- The work would mutate a file marked protected or owned by another
  participant.
- A destructive or hard-to-reverse operation is on the table.
- The owner said "ask before fixing" (set 2026-08-15).
- Multiple sources disagree and you can't reconcile them with
  available tools.

Default: when in doubt, ask. The cost of an unnecessary question is
one tap; the cost of a wrong guess is an entire redo.

## How do I finish?

Every consequential session ends with:

- **Verification:** the exact command + observed output for every
  claim about state, counts, sizes, or test results. No naked "30/30
  green" — paste the command.
- **Evidence:** file:line where the change lives, and the diff
  summary.
- **Exact changed state:** which files were touched, which were not,
  and what was deliberately left dirty.
- **UNKNOWNs:** anything you couldn't verify, named explicitly.
- **Next action:** the single next concrete step, not "continue."
- **Clean handoff:** if ending mid-investigation, write
  `.agent/HANDOFF.md` with confirmed facts, eliminated hypotheses,
  current hypotheses, and unresolved questions.
- **No inventions:** "I have not verified this" is a valid answer.
- **No recap of the user's words back at them.**

## Dogfood note (2026-09-12)

This onboarding packet was created as part of a Play-Nice experiment
requested from the MiniMax-m3 brain running in Kilo. What that
session observed:

- **Canonical-freshness check before any writing:** turn 1 caught a
  21-commit local-vs-remote drift; turn 2 caught a fresh 1-commit
  drift. Both times the project fast-forwarded with `git pull
  --ff-only` before any participant-pack authoring. The Play-Nice
  adoption pin (v0.6.0 @ `0cee065`) was honored unchanged through
  both updates — repo freshness and contract freshness are treated as
  separate questions.
- **Efficient project-truth discovery:** read 7 files
  (`CURRENT.md`, `project.yaml`, `adoption.yaml`, two participant
  packs, `participants/README.md`, `AGENTS.md`) — no `contractctl`
  available, no blind re-read of all 65 contracts.
- **Sibling participant preservation (not "general protected-WIP
  detection"):** an existing `big-pickle/` pack was discovered; the
  decision to leave it untouched and author a separate `minimax/`
  pack alongside it was made via a clarifying question with 3
  options, not a silent rewrite. The `big-pickle/` pack remained
  byte-identical to HEAD throughout. Generalizing this to "MiniMax
  detects protected WIP" would overstate the evidence — what was
  observed is narrower.
- **Harness/brain separation:** two distinct packs
  (`.project/participants/kilo/` for the harness, `.project/
  participants/minimax/` for the brain) with explicit
  `not_authoritative_for` boundaries and cross-references.
- **Self-validation caught a real failure mode:** the first draft
  placed markdown-table content inside files named `.yaml`. A
  deterministic `yaml.safe_load()` parse failed, the files were
  repaired into schema-conformant structured YAML before any
  commit. Lesson: parse generated structured files before accepting
  them, do NOT trust readable output as structurally valid.

## Anti-patterns observed in this project (do not repeat)

- `git add -A` in a shared checkout — sweeps in unrelated WIP.
- Bumping the adoption pin without verifying upstream via the live
  GitHub API.
- Fabricating test counts in summaries (the 2026-08-17 incident
  taught this lesson; see project history).
- Treating a participant pack as canonical project truth.
