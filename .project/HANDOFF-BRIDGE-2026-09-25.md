# Handoff: the Bridge, Step 1b "first light" (2026-09-25)

> **Superseded in part by [ADR-0008](../docs/adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../FRONTEND-INVENTORY.md).

**Read first:** [`PLAN.md`](PLAN.md) (the owner-approved plan) and then this file.
Review document with all evidence (sections A–L):
https://claude.ai/code/artifact/bd38f7ef-13ee-42e2-b700-9dc4079712f5

## Where things stand

- **Step 1b shipped to `main` via PR #68.** The Bridge replaces the Overview home.
  `GET /api/briefing` and `GET/PUT /api/place` are live in the code. The owner's
  **live instance is untouched**: it still runs a Station-era build, and any
  production cutover needs her explicit approval.
- **Owner reaction (2026-09-25):** "it feels a lot closer." Still off: **layout
  feels off**, **needs more life**, **too empty**. Nothing else was rejected.
- Screenshots: the owner's dev gallery, project `personal-world`, set "Bridge first
  light (Step 1b), 2026-09-25" (`gallery url personal-world`).

## How it works (one paragraph)

The briefing is what her world knows: six systems, each reported by a resident
from her canon in their own voice (`briefing_voice_lines.py`), plus a Keeper line.
The Keeper's art never encodes status (WORLD_KEEPER founding rule). The bridge is
`ui/src/screens/Bridge/` (`Bridge.tsx` layout, `StarMap.tsx`: the globe at the
centre with the crew on their decks). Contract: [`design/BRIEFING-CONTRACT.md`](design/BRIEFING-CONTRACT.md).
Sources today: Project Home (the `project home --json` CLI via `PW_PH_CLI`, or HTTP
via `PW_PH_URL` + a token env), the lab packet (`PW_LAB_CLI`), her journal
(entries she wrote, never machine lines), and discovery status. Media and news
are honest `not_configured`.

## Run it again

```bash
PW_PH_CLI=<project-home>/bin/project PW_LAB_CLI=<path to lab> scripts/dev-bridge.sh
# open http://127.0.0.1:4180/   (loopback only; dev auth bypass)
```

Gates: `uv sync --extra test --extra crypto && uv run pytest --timeout=30 -q`;
`uv run personal-world framework validate --json`;
`cd ui && npx tsc -p tsconfig.app.json --noEmit && npm run lint && npx vitest run`;
`PW_E2E_UI_PORT=4273 npx playwright test`. The override is needed because another
project's preview server often holds port 4173.

## Next (in order)

1. **1b.2: layout + life** (owner feedback). Planned by Claude:
   - The map is the hero. Remove the desktop lens list (the crew are the navigation).
     The briefing panel appears only when a resident is selected.
   - "Needs you" becomes a small calm dock by the Keeper ("5 need you: Bolt's
     holding them") that opens the tray, instead of a text block.
   - On the phone, the map is the first screen.
   - Life: each resident shows a small speech bubble with their line on the map.
     The sky tints with the time of day. Faint constellation lines connect
     residents with news to the Keeper. Motion stays governed by the motion
     preference (reduced by default per the accessibility contract); tell the
     owner that "subtle" motion in Settings makes the crew breathe.
   - Remove the dead-end nav entries (Interests, Projects, Computers) or route
     them to the Bridge. Replace the 🌍 assistant emoji with the Keeper.
2. **1c: fill it** (owner: "too empty"). Media (`native_media` already supports
   Plex/Sonarr/Radarr/Lidarr), calendars (`native_calendar`: ICS/CalDAV; work
   calendar via Microsoft Graph, delegated read-only), and Mira's interests
   (discovery sources). A research brief was run on 2026-09-25 to locate where
   these services and their key *names* live in homelab. If its result isn't
   recorded below, re-run it. The owner enters secret values in her secrets
   store herself; values never go in chat or tracked files.
3. Then 1d (deepen) and 1e (a preview on her phone). Production cutover only with
   her explicit approval.

## Open items

- The owner account's display name is the placeholder "Primary person". The
  Keeper won't say it. Setting her name in Settings makes the greeting personal.
- The World tree (Ratatoskr) reads "unknown" on a first visit, which is honest;
  consider a warmer first-visit line.
- `Records.tsx` still labels pinned records "Pinned to Overview" (the screen is
  now the Bridge). This needs an owner wording call; the tests assert the current text.
- `AGENTS.md` (the router) still names TRUE-NORTH as canonical direction. Updating
  it needs owner approval; CURRENT.md and PLAN.md already route correctly.

## Working method (owner directive)

Offload bulk work (research, inventories, first drafts, implementation drafts) to
cheap models with the `offload` CLI (DeepSeek v4.1 Flash used throughout). Claude
keeps design, integration, verification and conversation. Each slice ends with
phone + desktop screenshots in the gallery and a thumbs-up or "this feels wrong"
from the owner. Implementation details are the agent's call.
