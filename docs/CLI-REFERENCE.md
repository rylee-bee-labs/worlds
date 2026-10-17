# CLI reference

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the `personal-world` CLI surface and its wrappers · **Read this if:** you want to call the API from a script or bot without thinking about routes.

**In short:** the CLI's three commands (`api-manifest`, `api`, `do`), the friendly `do` wrappers, and the write-safety and exit-code rules. Every wrapper derives from the same route table the API serves, so it cannot drift.

Worlds has one CLI surface, bound to one source of truth.
Decision #19: *everything the product can do has a simple CLI wrapper
and an API route, and both derive from the same table* — so a small agent
or bot does not have to think, it just files things the right way.

The table is `src/personal_world/api_manifest.py`, the same one
`GET /api/manifest` serves as `endpoints`. Every wrapper declares the
manifest id(s) it files; its `kind`/`gate` are **read from that table**, never
restated. A binding check runs at import, so the map cannot silently drift.

## Three commands

| Command | What it does |
|---|---|
| `personal-world api-manifest` | The bot's map: 134 curated endpoints (as of 2026-09-26), each with its gate and the shell command that files it, plus explicit coverage counts. |
| `personal-world api <METHOD> <path>` | The generic authenticated escape hatch against a running local backend. Any row of the map is callable. |
| `personal-world do <noun> <verb>` | The friendly wrappers — one verb per action. Bare `do` prints the table below. |

The pre-existing top-level verbs (`status`, `journal`, `prefs`, `manifest`,
`history`, `worlds`, `updates`, `framework`, …) are untouched. The new
surface is additive: a name `cli.py` already owns is skipped, never clobbered
(`manifest` is the legacy provider/capability manifest, and `tests/test_framework.py`
pins its exact shape).

## 36 wrappers

| Command | Kind | Gate | Files | What it does |
|---|---|---|---|---|
| `personal-world do world status` | read | none | `GET /api/status` | world summary + capability statuses + actors (read-only) |
| `personal-world do world actors` | read | none | `GET /api/actors` | staff-directory view of every registered provider (read-only) |
| `personal-world do world intent` | write | step-up | `POST /api/world/intent` | file an intent write (propose by default) |
| `personal-world do world fact` | write | step-up | `POST /api/world/fact` | file a fact write (propose by default) |
| `personal-world do world policy` | write | step-up | `POST /api/world/policy` | file a policy write (propose by default; cemented policies still refuse) |
| `personal-world do journal list` | read | none | `GET /api/journal` | current version of each journal chain (read-only) |
| `personal-world do journal history` | read | none | `GET /api/journal/history` | full correction chain for one entry, oldest first (read-only) |
| `personal-world do journal audit` | read | none | `GET /api/journal/audit` | audit-log rendering of the journal (read-only) |
| `personal-world do journal write` | write | none | `POST /api/journal` | file a journal note (propose by default; nothing is written without --approve) |
| `personal-world do journal supersede` | write | step-up | `POST /api/journal/supersede` | file an append-only correction (propose by default) |
| `personal-world do reminders list` | read | none | `GET /api/reminders` | list reminders (read-only) |
| `personal-world do reminders add` | write | step-up | `POST /api/reminders` | file a reminder (propose by default) |
| `personal-world do proposals list` | read | none | `GET /api/proposals` | list proposals, newest last (read-only) |
| `personal-world do proposals get` | read | none | `GET /api/proposals/{proposal_id}` | one proposal in full (read-only) |
| `personal-world do proposals approve` | write | step-up | `POST /api/proposals/{proposal_id}/approve` | owner approval of a pending proposal (dry-run without --approve) |
| `personal-world do proposals reject` | write | step-up | `POST /api/proposals/{proposal_id}/reject` | reject a pending proposal (dry-run without --approve) |
| `personal-world do proposals execute` | write | proposal | `POST /api/proposals/{proposal_id}/execute` | execute an APPROVED proposal (dry-run without --approve) |
| `personal-world do prefs get` | read | none | `GET /api/prefs` | effective presentation preferences (read-only) |
| `personal-world do prefs schema` | read | none | `GET /api/prefs/schema` | the writable preference vocabulary and floors (read-only) |
| `personal-world do prefs set` | write | none | `PUT /api/prefs` | file a preference change (propose by default; minimum accessibility settings enforced) |
| `personal-world do interests list` | read | none | `GET /api/discovery/interests` | list discovery interests (read-only) |
| `personal-world do interests add` | write | none | `POST /api/discovery/interests` | file a new interest (propose by default) |
| `personal-world do discovery status` | read | none | `GET /api/discovery/status` | discovery engine status (read-only) |
| `personal-world do discovery sources` | read | none | `GET /api/discovery/sources` | list discovery sources (read-only) |
| `personal-world do discovery run` | read | none | `GET /api/discovery/discover` | fetch from sources now (a read per the manifest; may persist discovery feedback) |
| `personal-world do projects status` | read | none | `GET /api/projects/status` | project-estate status from the agent-sync sensor (read-only) |
| `personal-world do projects repos` | read | none | `GET /api/source-control/status` | native git status for every configured repository (read-only) |
| `personal-world do projects history` | read | none | `GET /api/source-control/history` | native git commit history, newest first (read-only) |
| `personal-world do projects propose-refresh` | write | step-up | `POST /api/source-control/refresh` | file an approved repository status refresh (propose by default) |
| `personal-world do capabilities list` | read | none | `GET /api/manifest` | capability/provider manifest — what exists, what is active (read-only) |
| `personal-world do capabilities health` | read | none | `GET /api/status` | per-capability health, the same map GET /api/status returns |
| `personal-world do chat send` | write | none | `POST /api/chat` | send a message to the companion (needs a running backend) |
| `personal-world do templates list` | read | none | `GET /api/brain/templates` | brain templates on disk (read-only) |
| `personal-world do auth status` | read | none | `GET /api/auth/session` | credential, principal and step-up readiness (never prints a secret) |
| `personal-world do auth session` | read | none | `GET /api/auth/session` | browser-session store summary; session ids are never printed |
| `personal-world do oidc status` | read | none | `GET /api/auth/oidc/config` | OIDC wiring state: not_configured | configured | unreachable | misconfigured |

## Coverage

- 34/134 curated rows have a friendly wrapper (as of 2026-09-26); the count in the table above is the wrappers themselves.
- 19 live rows are uncurated (reachable through `personal-world api`).
- The map reports this itself (`data.cli.coverage`); it does not imply completeness. Re-run `personal-world api-manifest` for today's numbers.

## Write safety

- Reads need nothing and change nothing.
- Writes file a **durable proposal** and exit `4` — nothing is mutated.
- To act, pass `--approve` **and** export `PW_STEP_UP_TOKEN=<instance token>`.
  A flag alone never mutates anything; a cemented policy still refuses.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | ok |
| `1` | error |
| `2` | usage |
| `3` | unavailable / not configured |
| `4` | gated: a proposal was filed, or approval/step-up is required (not an error) |

Generated against the live surface (`personal-world do`, `personal-world api-manifest`).
