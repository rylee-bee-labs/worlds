# Worlds — Frontend Inventory

> **Status:** Current · **Verified:** 2026-10-02 · **Canonical for:** what the browser interface is and where each piece lives · **Read this if:** you are about to work on the UI and want the map before the code

**In short:** The interface is the front door, a small React app in `ui/src/fd/` (ADR-0008): four landmarks (Home · Connect · Memory · Settings), served same-origin at `/` by the backend and mounted by `ui/src/main.tsx`. The old screens, components and mock API were deleted; git history is the archive. Anything that names `src/screens`, `src/components` or `ui/e2e/` is describing the old interface.

---

## The stack

| Piece | What | Where |
|---|---|---|
| **The app** | React 19 + TypeScript + Vite + Tailwind v4 (preflight only) | `ui/` |
| **Entry** | mounts `FdApp` inside the query and preferences providers | `ui/src/main.tsx` |
| **Front-door code** | everything the user sees | `ui/src/fd/` |
| **Styles** | one stylesheet: lab tokens (dark default, Daylight light set), shell, rows, strip, meters | `ui/src/fd/fd.css` |
| **Generated code** | tokens, icon sprite, API types (the build regenerates them) | `ui/src/generated/` |
| **Design tokens (truth)** | `design/tokens.json`, `design/themes/*.json` | → `ui/src/generated/tokens.{css,ts}` |
| **Worlds kit** | the framework-free design export other repos vendor | `ui/dist-kit/` (`npm run kit:build`, `kit:check`) |

## What is in `ui/src/fd/`

| File | What it is |
|---|---|
| `FdApp.tsx` | hash routing (`#home`, `#connect`, `#memory`, `#settings`; unknown or old ids fall back to Home), preference attributes on `<html>`, the Station decoration |
| `Shell.tsx`, `route.ts` | skip link, header / nav / main in fixed order; rail on desktop, bottom bar on phone |
| `Home.tsx` | greeting and briefing, whole-world strip, Edit Home, Needs you, Needs a look, Your life, Quietly working; independent loading; focus-hold |
| `Strip.tsx`, `Row.tsx`, `Meter.tsx` | the strip tiles, the instrument row with its drill-in, the seven meter types |
| `home-model.ts` | grouping rules (C6), briefing, greeting |
| `api.ts`, `safe-href.ts` | read hooks with per-request timeouts; link allow-list |
| `use-board-edit.ts`, `edit-model.ts` | Edit Home as C1 board writes (`PUT /api/config/board/{id}` with `If-Match`, 409 / 422 handling, Undo is another write) |
| `Connect.tsx`, `Memory.tsx`, `Settings.tsx`, `Tabs.tsx` | the other three landmarks and the shared tabs: Connect reads and writes providers, requests and cards, and lists actions and receipts read-only; Memory reads and writes kept, later and records; Settings holds preferences |
| `prefs.tsx`, `prefs-core.ts` | Words (Minimal / Short / Full), Density (Calm / Standard / Detailed), Station pack, theme, text size |
| `types.ts` | C1 / C2 / C6 types |
| `fixtures.ts`, `board-server.ts`, `msw.ts` | typed test fixtures (Home board and cards, Memory rows, Connect actions and receipts), an in-memory board server with the real rules, MSW handlers. **Tests only.** |

## API the UI uses

Home: `GET /api/boards/home`, `GET /api/needs-you`, `GET /api/cards/{id}`, `GET` and `PUT /api/config/board/{id}`. Connect: `GET /api/config/{kind}`, `GET` and `PUT /api/config/{kind}/{id}`, `POST /api/connect/try`, `POST /api/connect/preview`, `GET /api/actions`, `GET /api/receipts`. Memory: `GET` and `POST /api/memory/{table}`, `GET`, `PATCH` and `DELETE /api/memory/{table}/{id}`, `GET /api/memory/find`, `GET /api/memory/history`, `GET /api/memory/export/{table}`, `POST /api/memory/backup`. Shapes are in `docs/rebuild/CONTRACTS.md` (C2 envelope, C6 read API). `/api/pickup` is reserved; Pick up is omitted until it exists.

## Tests and commands (from `ui/`)

| Check | Command |
|---|---|
| Install | `npm ci` |
| Tokens | `npm run tokens:check` |
| Types | `npx tsc -b` |
| Lint | `npm run lint` |
| Unit | `npx vitest run` (files `src/test/**`; fd tests are `src/test/fd-*`) |
| Build | `npm run build` |
| Browser | `npx playwright test` — `e2e-fd/` against a mocked API and `e2e-fd-live/` against the real read API (`python -m personal_world.worlds.dev`); 390px and 1280px; axe with color-contrast on |
| Kit | `npm run kit:check`, `npm run kit:test:e2e` |

## Floors

Every UI change answers `docs/accessibility/ACCESSIBILITY_CONTRACT.md`: body 16px, labels at least 13px, 44px targets (56px strip tiles), a visible focus ring, no colour-only state (shape and word), motion off unless the device allows it, no horizontal overflow at 390px or 200% zoom. The manual screen-reader pass is a script, not yet a result: `docs/accessibility/FRONT-DOOR-SCREEN-READER-WALKTHROUGH.md`.

## Not here

Rooms, the Play-Nice contracts, shared CI workflows and the homelab live in other repos. The protected character art is not used by the front door. Station adds placeholder marks and the painted icon set from design-system (`ui/public/assets/painted/`, `ui/src/fd/PaintedIcon.tsx`): decoration beside words only, nothing with the pack off.
