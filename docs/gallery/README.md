# Screenshot gallery

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

> **Status:** Current · **Verified:** 2026-09-26 · **Canonical for:** what Worlds looks like today, screen by screen · **Read this if:** you want to see Worlds without running it, or you are refreshing the pictures after a UI change.

**In short:** Every Worlds screen, at phone (390px) and desktop (1440px)
widths, in the default starfield theme, plus the Bridge in every theme. The
pictures come from fake demo data, never from anyone's real Worlds.

## The gallery

"not yet" means the picture hasn't been taken yet. The table below is
rebuilt by `capture.mjs`; edit `manifest.json`, not the table.

<!-- gallery:start -->
| Screen | 390px | 1440px | State |
|---|---|---|---|
| **Bridge (home)**<br>Home: your guide's briefing, what needs you, and each room as a doorway. Other themes: [doorways](shots/bridge/doorways-390.png), [station](shots/bridge/station-390.png), [moss](shots/bridge/moss-390.png), [ocean](shots/bridge/ocean-390.png), [plain](shots/bridge/plain-390.png), [daylight](shots/bridge/daylight-390.png). | [![The Bridge: a short briefing at the top, a Needs you tray, and room doorway cards with their status in words. (390px)](shots/bridge/starfield-390.png)](shots/bridge/starfield-390.png) | [![The Bridge: a short briefing at the top, a Needs you tray, and room doorway cards with their status in words. (1440px)](shots/bridge/starfield-1440.png)](shots/bridge/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **A room's drawer (Studio)**<br>Look inside a room: its status in words, what changed, and what needs you. Links open on the room's own site. | [![The Studio drawer open beside the Bridge, showing a need, cards with tone words, and an Open Studio button. (390px)](shots/room-drawer-studio/starfield-390.png)](shots/room-drawer-studio/starfield-390.png) | [![The Studio drawer open beside the Bridge, showing a need, cards with tone words, and an Open Studio button. (1440px)](shots/room-drawer-studio/starfield-1440.png)](shots/room-drawer-studio/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Workshop drawer with Secrets**<br>The Workshop's Secrets section, for the owner only: key names and health, never a value. | [![The Workshop drawer with a Secrets section: the station's health in words and key names in groups. (390px)](shots/room-drawer-workshop-secrets/starfield-390.png)](shots/room-drawer-workshop-secrets/starfield-390.png) | [![The Workshop drawer with a Secrets section: the station's health in words and key names in groups. (1440px)](shots/room-drawer-workshop-secrets/starfield-1440.png)](shots/room-drawer-workshop-secrets/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Secrets: waiting for you**<br>An agent asked for a secret. Nothing is shared until you type it on Project Home's page. | [![The Workshop drawer's Secrets section with a request card and an Enter it in Project Home button. (390px)](shots/secrets-waiting/starfield-390.png)](shots/secrets-waiting/starfield-390.png) | [![The Workshop drawer's Secrets section with a request card and an Enter it in Project Home button. (1440px)](shots/secrets-waiting/starfield-1440.png)](shots/secrets-waiting/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **A room Worlds can't reach**<br>A room that isn't answering says so and when it last answered. Nothing from it is shown as current. | [![The Cellar drawer saying Worlds can't reach it and when it last answered. (390px)](shots/unreachable-room/starfield-390.png)](shots/unreachable-room/starfield-390.png) | [![The Cellar drawer saying Worlds can't reach it and when it last answered. (1440px)](shots/unreachable-room/starfield-1440.png)](shots/unreachable-room/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Find a room (12 or more rooms)**<br>With 12 or more rooms, a search box appears and says how many rooms match. | [![The Rooms section with a Find a room box containing 'st' and a line saying how many rooms match. (390px)](shots/find-a-room/starfield-390.png)](shots/find-a-room/starfield-390.png) | [![The Rooms section with a Find a room box containing 'st' and a line saying how many rooms match. (1440px)](shots/find-a-room/starfield-1440.png)](shots/find-a-room/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **No rooms yet**<br>Before any room is connected, the Bridge says so and explains how rooms connect. | [![The Rooms section saying there are no rooms yet, with a How rooms connect button. (390px)](shots/no-rooms/starfield-390.png)](shots/no-rooms/starfield-390.png) | [![The Rooms section saying there are no rooms yet, with a How rooms connect button. (1440px)](shots/no-rooms/starfield-1440.png)](shots/no-rooms/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Ask about a room in Chat**<br>Ask about a room: Chat opens with a question already written in the box. You send it. | [![The Chat screen with a question about Studio written in the message box, not yet sent. (390px)](shots/ask-in-chat/starfield-390.png)](shots/ask-in-chat/starfield-390.png) | [![The Chat screen with a question about Studio written in the message box, not yet sent. (1440px)](shots/ask-in-chat/starfield-1440.png)](shots/ask-in-chat/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Memory**<br>Memory: your journal and records, and finding things in them. | [![The Memory screen with a note box and recent journal entries. (390px)](shots/memory/starfield-390.png)](shots/memory/starfield-390.png) | [![The Memory screen with a note box and recent journal entries. (1440px)](shots/memory/starfield-1440.png)](shots/memory/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Chat**<br>Chat with your companion. It can look things up; anything it wants to change becomes a proposal you approve. | [![The Chat screen with the companion's name in the header and the message box. (390px)](shots/chat/starfield-390.png)](shots/chat/starfield-390.png) | [![The Chat screen with the companion's name in the header and the message box. (1440px)](shots/chat/starfield-1440.png)](shots/chat/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Settings**<br>Settings: your crew, messages, look and feel, and more. | [![The Settings screen with the Your crew card, message choices and theme swatches. (390px)](shots/settings/starfield-390.png)](shots/settings/starfield-390.png) | [![The Settings screen with the Your crew card, message choices and theme swatches. (1440px)](shots/settings/starfield-1440.png)](shots/settings/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Crew**<br>Crew: choose your companion, and put a keeper and a doorway on each room. | [![The Crew page with companion cards and a keeper and doorway choice for each room. (390px)](shots/crew/starfield-390.png)](shots/crew/starfield-390.png) | [![The Crew page with companion cards and a keeper and doorway choice for each room. (1440px)](shots/crew/starfield-1440.png)](shots/crew/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **People**<br>People: who lives in this World, each role written as what that person can do, inviting someone, and handing the World over. | [![The People page listing Sam, Jo, Alex, Robin and Kit, each with a plain sentence about what they can do. (390px)](shots/people/starfield-390.png)](shots/people/starfield-390.png) | [![The People page listing Sam, Jo, Alex, Robin and Kit, each with a plain sentence about what they can do. (1440px)](shots/people/starfield-1440.png)](shots/people/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Let someone help you**<br>Let someone help you: choose who and for how long, stop it any time, and see what they did. | [![The helpers page with a form to choose a person and how long, a list of who is helping now with Stop now buttons, and a Who helped me list. (390px)](shots/helpers/starfield-390.png)](shots/helpers/starfield-390.png) | [![The helpers page with a form to choose a person and how long, a list of who is helping now with Stop now buttons, and a Who helped me list. (1440px)](shots/helpers/starfield-1440.png)](shots/helpers/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Interests (moving to Candy)**<br>Interests: discovery as it lives in Worlds today, before it moves to the Candy room. | [![The Interests screen with a list of followed interests. (390px)](shots/interests/starfield-390.png)](shots/interests/starfield-390.png) | [![The Interests screen with a list of followed interests. (1440px)](shots/interests/starfield-1440.png)](shots/interests/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Projects (Hive Works not connected)**<br>Projects shows the Hive Works company. When Hive Works isn't connected, the page says so instead of showing anything as current. | [![The Projects page saying Hive Works isn't connected to this World yet. (390px)](shots/projects-placeholder/starfield-390.png)](shots/projects-placeholder/starfield-390.png) | [![The Projects page saying Hive Works isn't connected to this World yet. (1440px)](shots/projects-placeholder/starfield-1440.png)](shots/projects-placeholder/starfield-1440.png) | captured 2026-09-27 @ 3d739fa |
| **First Light: welcome**<br>First Light, the first-run setup, starts with a plain welcome. | [![The First Light welcome step with a Let's begin button. (390px)](shots/first-light/starfield-390.png)](shots/first-light/starfield-390.png) | [![The First Light welcome step with a Let's begin button. (1440px)](shots/first-light/starfield-1440.png)](shots/first-light/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **First Light: make yourself comfortable**<br>Choose a theme, larger text, gentle motion, and whether the crew is on. | [![The First Light comfort step with three theme choices and three checkboxes. (390px)](shots/first-light-comfort/starfield-390.png)](shots/first-light-comfort/starfield-390.png) | [![The First Light comfort step with three theme choices and three checkboxes. (1440px)](shots/first-light-comfort/starfield-1440.png)](shots/first-light-comfort/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **First Light: pick a companion**<br>Pick a companion, or keep the Assistant's plain voice. | [![The First Light companion step with the Assistant chosen. (390px)](shots/first-light-companion/starfield-390.png)](shots/first-light-companion/starfield-390.png) | [![The First Light companion step with the Assistant chosen. (1440px)](shots/first-light-companion/starfield-1440.png)](shots/first-light-companion/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
| **Sign in**<br>Sign in to Worlds. With an identity provider set up, a passkey comes first and the access code is the fallback. | [![The Worlds sign-in page with a field for the access code. (390px)](shots/login/starfield-390.png)](shots/login/starfield-390.png) | [![The Worlds sign-in page with a field for the access code. (1440px)](shots/login/starfield-1440.png)](shots/login/starfield-1440.png) | captured 2026-09-26 @ 74ae381 |
<!-- gallery:end -->

## How it works

- **[`manifest.json`](manifest.json)** says what to capture: each entry has an
  `id`, a `title`, how to reach it (`area` = the navigation button, plus
  optional `steps` such as opening a room's drawer), which `themes` and
  `widths`, a `caption`, `alt` text, and a `status` (`wanted` or `captured`,
  with the date and commit).
- **[`capture.mjs`](capture.mjs)** builds nothing itself. It starts the same
  deterministic mock API the UI tests use (`ui/scripts/e2e-api.mjs`) and the
  production preview build, visits each entry, and saves
  `shots/<id>/<theme>-<width>.png`.
- **[`capture-server.mjs`](capture-server.mjs)** takes the server-rendered
  pages (First Light and sign-in) from a throwaway local Worlds. It refuses
  any address that isn't this machine.
- **[`showcase.mjs`](showcase.mjs)** frames pictures from `shots/` for the
  main README (`showcase/`): a rounded window or phone on a starry
  background, with one of the crew peeking in. The images carry no words;
  the captions live in the README.
- **`shots/`** holds the pictures, one folder per entry. An entry can use a
  made-up data variant (`fixture`: `many-rooms`, `no-rooms`), `steps`
  (`click` or `fill`) and `scroll_to` to show a particular state.

## Refreshing the pictures

Run from `ui/`:

```bash
npm run build
node ../docs/gallery/capture.mjs                 # everything capturable
node ../docs/gallery/capture.mjs --only bridge   # one entry
node ../docs/gallery/capture.mjs --all-themes    # every theme for every entry
node ../docs/gallery/capture.mjs --table-only    # rebuild the table only
node ../docs/gallery/showcase.mjs                # the framed README images
```

For First Light and sign-in, build the app (`bash scripts/build-app.sh` from
the repo root), start a throwaway Worlds with fresh directories, then run
`capture-server.mjs` (instructions at the top of the script).

Then look at the new pictures before committing them.

## Rules

- **Mock data only.** This repo is public. Never capture the owner's Worlds
  or any instance with real data, and never commit a picture that shows a
  real name, address, token, hostname or IP.
- **Server-rendered pages** (`/setup` for First Light, `/login`) aren't served
  by the preview build, so `capture.mjs` skips them; `capture-server.mjs`
  takes them from a throwaway local Worlds, never a real one.
- **To add a screen**, add an entry to `manifest.json` with a caption and
  `alt` text that describe what a person sees, then run the capture.
- **Pictures are a record, not a spec.** Design authority stays in
  [`.project/design/CURRENT.md`](../../.project/design/CURRENT.md); the
  Worlds kit's own component preview is `ui/dist-kit/preview.html`.
