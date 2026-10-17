# ui — the Worlds front door

> **Status:** Current · **Verified:** 2026-10-13 · **Canonical for:** frontend commands, the build pipeline and how the API types/spec are generated · **Read this if:** you are about to build, test or wire the browser interface.
>
> **Superseded in part by [ADR-0008](../docs/adr/0008-front-door.md) (2026-10-01):** this file used to be titled "Station vNext UI" and described a Station-era interface. The front door is `Home · Connect · Memory · Settings`; the current map of screens and files is [`FRONTEND-INVENTORY.md`](../FRONTEND-INVENTORY.md). Station survives only as a theme package.

React + TypeScript + Vite + Tailwind v4 frontend for the **front door**
(`ui/src/fd/`). The app is served same-origin at `/` by the backend; this
README covers running and building it locally.

## Quickstart

```bash
# Install dependencies (first time only)
npm ci

# Start dev server (proxies API to backend on :8000)
npm run dev

# Build for production
npm run build
```

Dev server runs at `http://localhost:5173` and proxies `/api` and `/healthz`
to `http://127.0.0.1:8000` (the FastAPI backend) — see `vite.config.ts`
(`VITE_API_PROXY_TARGET` overrides the target, `PW_VITE_BASE` sets a deploy
path prefix).

## Prerequisites

- Node.js 22+ (CI pins 22)
- Backend on port 8000. The old `personal-world api` verb is retired: the
  front-door app is `uvicorn personal_world.worlds.production:app_from_env --factory`,
  or just `./install.sh` from the repository root.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `""` (same-origin) | API base URL. Leave empty when using the Vite proxy. |
| `VITE_API_PROXY_TARGET` | `http://127.0.0.1:8000` | Dev/preview proxy target (see `vite.config.ts`). |
| `PW_VITE_BASE` | `/` | Deploy-time URL prefix, e.g. `/vnext/`. |

## Build Pipeline

```
npm run build = tokens:generate → icons:generate → api:generate → tsc -b → vite build
```

| Step | What it does |
|---|---|
| `tokens:generate` | Reads `design/tokens.json` + `design/themes/*.json` → generates `src/generated/tokens.css` + `tokens.ts` |
| `icons:generate` | Generates the icon sprite module `src/generated/icons.ts` |
| `api:generate` | Reads `src/generated/openapi.json` → generates `src/generated/api-types.ts` (typed API) |
| `tsc -b` | Type-checks all TypeScript (strict) |
| `vite build` | Produces `dist/` |

## Updating the API Spec

`src/generated/openapi.json` is **generated, not hand-maintained** (this
file used to say otherwise, and name module paths that are gone). It is
written from the live front-door app
(`personal_world.worlds.production:create_app`) by:

```sh
uv run python scripts/gen-openapi.py                  # regenerate the spec
uv run python scripts/contract-drift-check.py         # read-only: does it still match the app?
```

If the check reports drift, regenerate — do not edit the JSON or the
generated TypeScript by hand. The committed route inventory
(`scripts/route-inventory.json`, every `/api` route plus `/healthz` with
its auth level) is regenerated the same way:

```sh
uv run python scripts/contract-drift-check.py --write
```

When the backend adds or changes endpoints, also update the front-door
client in `src/fd/api.ts` and the MSW handlers in `src/fd/msw.ts` (mocks
must mirror the real envelope or they teach fiction).

## Tests and gates

| Check | Command (from `ui/`) |
|---|---|
| Install | `npm ci` |
| Generated tokens unchanged | `npm run tokens:check` |
| Types | `npx tsc -b` |
| Lint | `npm run lint` |
| Unit | `npx vitest run` (`src/test/**`, fd tests are `src/test/fd-*`) |
| Build | `npm run build` |
| End-to-end | `npx playwright test` |
| Worlds kit | `npm run kit:build`, `npm run kit:check`, `npm run kit:test:e2e` |

Playwright runs the front-door suites (see `playwright.config.ts`):
`e2e-fd/` against a mocked API (`page.route`, fixtures in
`src/fd/fixtures.ts`) on a Vite dev server (port 4180, no backend), and
`e2e-fd-live/` against the real read API (`python -m personal_world.worlds.dev`)
through the Vite proxy on port 4181. Phone (390) and desktop (1280) are
both first-class. `ui/e2e/`, `ui/kit/` and `ui/uat/` are the older
Station-era suites and helpers; they are not part of the default
`npx playwright test` projects.

## Project Structure

```
ui/
├── src/
│   ├── app/            # QueryProvider
│   ├── data/           # TanStack Query client
│   ├── fd/             # Front-door UI (shell, screens, CSS, API client, fixtures)
│   ├── generated/      # Auto-generated (tokens, icons, API types, OpenAPI spec)
│   └── test/           # Vitest unit tests
├── e2e-fd/             # Playwright e2e against the mocked API
├── e2e-fd-live/        # Playwright e2e against the real read API
├── e2e/, kit/, uat/    # Station-era suites/helpers (legacy)
├── scripts/            # Token, icon + API type generation
├── public/             # Static assets (fonts, images, icons)
└── dist/               # Production build output
```

## Key Technologies

- **React 19** + **TypeScript 7**
- **Vite 8** (build) + **Oxlint** (lint)
- **Tailwind v4** (styling via CSS variables)
- **React Aria Components** (accessible primitives)
- **TanStack Query** (server state)
- **openapi-fetch** + **openapi-typescript** (typed API)
- **Style Dictionary** (token pipeline)
- **Storybook 10** (component dev)
- **Vitest 5** + **Playwright** (testing)
- **MSW** (mocking)

## Accessibility

All UI follows the accessibility contract in
[`docs/accessibility/ACCESSIBILITY_CONTRACT.md`](../docs/accessibility/ACCESSIBILITY_CONTRACT.md):

- 44×44px minimum hit areas
- Focus always visible (teal ring)
- Skip-to-main-content on every page
- Status by text, never color alone
- No animation/shimmer loading states
- Keyboard-operable throughout

Which doc owns which command or claim:
[`docs/vnext/docs-truth.md`](../docs/vnext/docs-truth.md).