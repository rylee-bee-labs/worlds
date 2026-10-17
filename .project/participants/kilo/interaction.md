# Kilo — Interaction contract (how a session should behave)

Status: PROVISIONAL — observed 2026-09-12. Update as new sessions reveal
behavior not yet captured here.

## The single most important rule

> **Tool access is capability, not authorization.**

Kilo having bash, file, git, MCP, or web tools does NOT mean it is
allowed to use them for mutation without explicit owner authority. The
harness exposes; the project authorizes.

## Confirmation gates (do not try to bypass)

| Action class                       | Behavior                                                |
| ---------------------------------- | ------------------------------------------------------- |
| Read-only shell                    | Runs.                                                   |
| `git status`, `log`, `diff`, `fetch` | Runs.                                                 |
| `git pull --ff-only`               | Confirms per command.                                   |
| `git add <path>`, `git commit`     | Confirms per command.                                   |
| `git push`, `merge`, `reset --hard` | Confirms per command; should generally be preceded by Rylee saying "deploy" / "merge" / etc. |
| File write to a NEW path           | Confirms once per path.                                 |
| File overwrite / `Edit` on existing | Confirms on first occurrence; reads file before edit.    |
| Destructive (`rm`, `mv` overwrites, `--force`, force-push) | Asks before doing.                              |
| Anything ambiguous                  | Ask via the `question` tool with 2-3 options.          |

Confirmation prompts in Kilo are one-shot: the user must approve each
mutating command individually. There is no "always allow" rule that
spans mutating git commands.

## When to ask the human via the question tool

- Scope is ambiguous (multiple valid paths).
- Authority is unclear (especially across participant packs).
- Destructive or hard-to-reverse operations.
- An existing participant pack would be mutated by your work.
- An UNKNOWN would be papered over by guessing.
- Task expansion beyond the original brief.

Default: when in doubt, ask. The cost of an unnecessary question is one
tap; the cost of a wrong guess is an entire redo.

## Output discipline (matrix-friendly defaults)

Kilo's renderer collapses tool bodies by default; expand on demand
(`Ctrl+P` → "Toggle tool details"). For non-trivial turns:

- Lead with a table or one-sentence summary.
- One blank line between every paragraph and code block.
- Code blocks for any path, command, JSON, log line longer than ~80 chars.
- Status by neutral language ("healthy / degraded / unhealthy"), not
  traffic-light hues.
- No emoji in commit messages, repo files, or generated docs.
- No recap of the user's own words back to them.
- Open with `YOU:` / `NEXT:` (or status matrix) on long turns;
  close the same way. Cancel must be discoverable when work spans
  more than one tool call.

## Session start (recommended order)

1. Read the always-loaded `AGENTS.md` (project) and any user-profile
   file (e.g. `rylee.md`).
2. Read `.project/README.md` and `.project/CURRENT.md` for project
   state.
3. Inspect `.project/contracts/adoption.yaml` and confirm the adoption
   pin (do not bump it without explicit owner approval).
4. List `.project/participants/` and load only task-relevant packs.
5. Run a memory check (`memory_memory_search` or
   `memory_journal_check`) if relevant to the task.
6. Pull mem0 profile (`preferences_get_profile`) for owner preferences
   that may not yet be folded into the always-loaded files.
7. Begin work; persist durable state via git + memory ingest.

## Session end

- Update `.agent/STATE.md` with what is true now (overwrite, concise).
- Commit work with explicit paths; never `git add -A` in a shared
  checkout.
- Optionally run `scripts/safe-commit.sh -m "msg" <paths...>` for the
  guardrails.
- If onboarding improvements were discovered, propose them as a future
  PR — do not silently rewrite canonical files.

## Anti-patterns (do not do)

- Invent values to complete a summary pattern. If you did not run the
  command, do not make the claim. "I have not verified this" is a
  valid output.
- Recap the user's words back at them.
- Promise "30/30 green" without the exact command + output.
- Absorb unrelated dirty work into a focused change.
- Re-adopt an already-adopted project just because you arrived.
- Rewrite another participant's pack without their explicit consent.
- Treat the loaded brain's identity as the harness's identity.
