# Porting and contributing: what you can replace, and what must stay

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** which parts of Worlds can be replaced, and what any port must keep · **Read this if:** you want to move, extend, or contribute to Worlds.

**In short:** four things any port must keep (the core principles, the
accessibility requirements, accurate states, and the Play-Nice contracts), and
the parts underneath them you can replace. It is a how-to, not a roadmap.

## What any port must keep
1. **The core principles:** start with the smallest thing that works reliably;
   show more detail only when asked; gentle by default; usable by everyone at
   any level of energy or skill.
2. **The accessibility requirements** (`docs/accessibility/ACCESSIBILITY_CONTRACT.md`),
   enforced by tests.
3. **Accurate states:** no fake data; explicit empty / loading / not_configured /
   unavailable / stale / unknown states; writes always need approval
   (observe → propose → approve → act).
4. **The Play-Nice contracts** (`.project/contracts/adoption.yaml`).

## What you can replace (keep everything else)
| Part | Where | Replace it with |
|---|---|---|
| Frontend | `ui/` (React app, served at `/`) | any UI that uses the API |
| API | `/api/manifest` (the full route list) | your own client |
| Capabilities | `src/personal_world/providers/` + registry | any backend or external service |
| Model | `reasoning` capability (local Ollama by default) | any model that can call tools |
| Storage | `data/` (`docs/IDENTITY-BOUNDARY.md`) | any durable store |
| Sign-in | local token/session **or** generic OIDC | any identity provider |
| Rooms | the Play-Nice ROOM contract `room/0` (`.project/contracts/adoption.yaml`) | any separate service that implements the contract |
| Templates and personas | `config/prompts/**` (plain markdown) | your own words |

## Contributing
- One checkout per task; never `git add -A`; use `scripts/safe-commit.sh`.
- Tests are the gate: `uv run --extra test --extra crypto pytest --timeout=60 -o addopts="" -q`
  and `uv run personal-world framework validate --json`.
- Dev loop: `scripts/dev.sh up` / `newest` / `wipe` / `status` / `logs`.
- New user-facing copy: plain words, active voice, no guilt, no jargon.

## Porting checklist
- [ ] Keep the four items under "What any port must keep".
- [ ] Re-implement against `/api/manifest`, not against internals.
- [ ] Keep accurate state labels and gated writes in the new location.
- [ ] Re-run the accessibility tests on the new UI.
- [ ] Ship a `QUICKSTART` equivalent: one command, wizard, no manual tokens.
