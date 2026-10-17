# Handoff — Orchestration (UAT Round 1 complete)

> **HISTORICAL (2026-09-12). Not the current entry point.** Verified stale
> 2026-09-15: the test counts (578/356/43) and the NEXT list predate the
> Workshop v3 convergence and integration-truth eras. Start at
> [`CURRENT.md`](./CURRENT.md) ("2026-09-15 finish-pass truth") instead.
> Kept for provenance: it records the UAT round, the two standing owner
> rules, and the deployment topology of that time.

**Task chain:** `project-worlds-test-environment` → T15 cutover →
settings fixes → cache-revalidation → UAT round 1 closure.
**Written:** 2026-09-12, agent GLM-5.3 Flash session.
**Next agent: start here.** This file records what is true, what is
running, and what to do next. Do not re-derive it.

## Result of the round

Rylee walked the deployed product (first-run setup, Today, Journal,
chat, the seam-hunting walk) on the isolated test environment and
**passed this round of UAT** ("this passes this round of UAT"). Her
words on Settings ("still feels like an afterthought, some of the
elements just don't work right") drove one real fix round; the cache
trust issue she hit drove another. She also set two standing rules —
both recorded in `.project/DECISIONS.md`:

1. **UAT data discipline:** no persisted user data in the test
   environment until she calls the product at least beta. Every walk
   starts from a verified clean slate (`down -v`, then `up -d`, then
   `GET /healthz` must show `"setup_needed":true`, printed to her).
   Persistence only for a named test use case, wiped right after.
   Decision entry: 2026-09-12, "UAT data discipline".
2. **Browser-trust contract:** no `immutable` cache anywhere — every
   asset revalidates every load (explicit ETag/If-None-Match 304
   handling, since starlette 1.6.0 has none natively — verified by
   probe before relying on it). Decision-level rationale lives in the
   commit message of `bbd1b5f` and `tests/test_frontend_serving.py`.

She also stated she is fine working with the shell directly for now
("I'm ok with the shell for now until every UI bug is ironed out") —
do not interpret this as a request for more UI polish passes ahead of
infrastructure honesty.

## What landed (all on main, CI green, images published)

| Commit | What |
|---|---|
| `07b5dd3` | Tidy: post-rename URL sweep, dead .gitea CI removed, stale runbook wording |
| `20697fe` | **T15 cutover** — legacy UI deleted; React SPA is the only frontend; `PW_FRONTEND` switch removed; missing-dist = honest 503, no fallback UI. Legacy-return regression guards added. |
| `ec29e85` | Settings fixes: server-truth refetch after every pref write; optimistic companion reverted on failure; dead theme-pack selector removed. |
| `13fdb67` | Decision record: UAT data discipline (standing rule). |
| `bbd1b5f` | No immutable cache: explicit ETag revalidation + 304 + logging on all static files. |

Verification state at handoff: backend **578 passed**, frontend **356
passed**, e2e **43 passed** (incl. axe), framework validate **healthy**,
CI validate **success** on main. Legacy-UI guards: `TestLegacyUiCannotReturn`,
`test_dist_contains_no_legacy_ui`, `test_no_frontend_mode_switch`.

## Deployment truth

- **Test environment:** `~/project-worlds-test/` on the Bazzite host
  (compose project `project-worlds-test`, host port **18080**, volume
  `project-worlds-test-data`, token in `./.env` chmod 600 — value never
  printed anywhere).
- **Current image:** `ghcr.io/rylee-bee/personal-world:sha-bbd1b5f0527b9c4facaf129595e3315c0010913e`
  (live-verified: healthz green, asset revalidation answers 304).
- **State at handoff:** volume **wiped** per the standing rule; the
  container is up on a blank world (`setup_needed:true` proof above).
  The next walk begins from the setup wizard.
- **Hermes (co-resident agent):** gateway PID 1662422 ran untouched
  through every pass; its ports (8081/8082 llama endpoints, 5173,
  6006) were never occupied. Keep it that way.

## Known defects (real, diagnosed, unfixed)

1. **Setup-created tokens do not survive a restart.** `POST /api/setup`
   writes the token to `/data/.env` (a file **nothing reads at boot**)
   and mutates `os.environ` in the live process; a container restart
   reverts auth to the compose-supplied `PW_API_TOKEN`, 401-ing the
   token the wizard gave the user. On the test instance the two
   coincide by construction, so it is invisible there — in production
   with a changed compose token it would lock the owner out. **This is
   the top item for the P2 auth pass** (`.project/CURRENT.md` already
   scopes P2: OIDC seam, sessions, step-up). Interim truth: the
   compose env token is the stable credential on any deployment.
2. **Wizard-token UX:** first-run asks the human to understand
   "login token / vault passphrase" — the desired SSO-first flow is a
   design slice, deferred with P2 (owner-approved direction: simplify
   now, auto-generate internal credentials, move manual tokens behind
   an Advanced path; recorded in the acceptance-fix task brief).
3. **Settings leftovers (deferred by decision):** accent pref is
   schema-served but has no control and no React consumer; theme-pack
   artwork application deferred until packs exist that the companion
   vocabulary can address.

## Dependency/tooling posture (checked this session, no migration needed)

Everything is at latest stable: fastapi 0.141.1, starlette 1.6.0,
uvicorn 0.52.4, pydantic 2.13.5, httpx 0.28.1, pytest 9.1.1,
cryptography 50.0.0; `uv lock --check` clean. Node: react 19.2
(latest 19.3 patch), vite 8.2 (latest 8.3 minor), react-router-dom
7.18.3 = latest, tailwind 4.3.3 = latest, vitest 5.0.0 = latest;
`npm audit` 0 vulnerabilities (runtime + dev). Deliberate pins:
TypeScript `~6.0.2` (TS 7.0.2 exists — major bump deferred, its own
bounded pass), CI Node 22 LTS, uv pinned in CI (0.11.28 vs local
0.11.33 — lockfile-gated, harmless). Patch bumps (react 19.3, vite
8.3, playwright 1.63) = quiet maintenance slice, not urgent.

## NEXT (legitimate next actions, in order)

1. **Rylee decides** whether the next UAT round happens on a fresh
   walk (clean slate is already deployed and waiting at
   `http://<host>:18080/setup`).
2. **Next bounded agent slice (suggest): P2 auth groundwork** — the
   restart-survivable token fix (1 above) is small, concrete, and
   removes the sharpest known lockout risk. Do it as its own commit
   with its own tests; do not absorb other work into it.
3. **After that:** SSO-first setup design slice (owner input needed on
   provider choice), then the deferred patch-bump maintenance slice.
4. **Do not start:** product redesign, new frontend phases, or any
   feature work ahead of Rylee's next walk. North star: the product
   tells us what needs work; we don't preempt it.

## Operational quick reference

```bash
# clean slate (standing UAT rule):
cd ~/project-worlds-test
podman compose -p project-worlds-test down -v
podman compose -p project-worlds-test up -d
curl -s http://localhost:18080/healthz   # must show setup_needed:true

# redeploy on a new published sha:
sed -i 's|PW_IMAGE=.*|PW_IMAGE=ghcr.io/rylee-bee/personal-world:sha-<NEW_SHA>|' .env
podman compose -p project-worlds-test up -d

# validation gates (from repo):
uv run pytest --timeout=30
uv run personal-world framework validate --json
cd frontend && npm run test && npx playwright test
```