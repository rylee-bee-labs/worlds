# The Worlds library

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

> **Status:** Current · **Verified:** 2026-09-27 · **Canonical for:** nothing (plain-words teaching; each book points to the doc that is canonical) · **Read this if:** you want to understand how Worlds works and why, without reading code.

**In short:** short books that teach how Worlds works: how the pieces fit,
how the screens are layered, and the lessons learned the hard way building
it. They are written for people first (any tech level), and agents may read
them too.

**Every book works for technical and non-technical readers alike,** in
layers:

1. **In short:** one plain sentence (the `short` line in the header).
2. **Plain words:** the ordinary pages. No jargon; any word that needs
   explaining goes in the next layer.
3. **Words to know:** each official term with its plain meaning, so you can
   talk to experts and search the web. A page that starts `## Words to know`.
4. **Under the hood:** files, endpoints and code for technical readers. A
   page that starts `## Under the hood`; the app may fold it away.

A book may also have a **voice** page: the keeper's own character saying it
their way. It starts `## In <name>'s words`. It's never the only place
something is explained.

**Worlds is the home of a bigger library.** Every connected app can keep its
own shelves in the same shape: the Play-Nice `library` contract
(`library/0`). Worlds gathers them (`GET /api/library`) and shows each
under its keeper, side by side and never merged. This folder is Worlds'
own shelf.

Each book is a Markdown file with a small header (`title`, `kind: book`,
`order`, `for`, `short`) and pages separated by `* * *`, the same format as
VEFR's Library. Worlds bundles them into the app (`ui/src/data/library.ts`).

| # | Book | What it teaches |
|---|---|---|
| 01 | [How Worlds fits together](01-how-worlds-fits-together.md) | The small core, the providers, and the rooms around it |
| 02 | [Rooms](02-rooms.md) | How other apps show up in Worlds, and why Worlds never copies them |
| 03 | [Live, both ways](03-live-both-ways.md) | How a change in one app shows up in Worlds within seconds |
| 04 | [How the screens are layered](04-how-the-screens-are-layered.md) | Tokens, themes, your own settings, and the parts nobody can change |
| 05 | [Honest by default](05-honest-by-default.md) | "Unknown" is an answer; nothing claims to be fine without proof |
| 06 | [Secrets](06-secrets.md) | Say where a secret lives, never what it is |
| 07 | [Every setup checks itself](07-every-setup-checks-itself.md) | No config files to edit; the same tools for everyone |
| 08 | [Who can do what](08-who-can-do-what.md) | Roles, permissions, helpers, and what agents may never do |
| 09 | [Notifications](09-notifications.md) | Three tiers, quiet hours, private notes, and iPhone |
| 10 | [How a change reaches you](10-how-a-change-reaches-you.md) | From a pull request to the app on your phone |
| 11 | [Lessons learned the hard way](11-lessons-learned-the-hard-way.md) | The mistakes that shaped the rules |
| 12 | [The candy dispenser](12-the-candy-dispenser.md) | How Candy finds things and learns what you like |
| 13 | [How integrations work](13-how-integrations-work.md) | The four ways Worlds connects to other things |
| 14 | [The vault](14-the-vault.md) | A locked box for secrets, and the estate's bigger one |
| 15 | [Confirm it's you](15-confirm-its-you.md) | Step-ups: proving it's you again before something important |
| 16 | [Making the UI](16-making-the-ui.md) | How a screen gets made, and the rules every screen follows |
| 17 | [How the interface was made](17-how-the-interface-was-made.md) | Boards, tokens, themes, the rules, the gallery and the handoffs, from the design lane |

**Adding a book:** keep it short (a page is a few short paragraphs), use
plain words, say what is true today, and fill all four layers. Name the
canonical doc under "Under the hood". `ui/src/test/library.test.ts` fails
when a book has no `short` line or doesn't start with a plain page. When a book and a canonical doc disagree,
the canonical doc wins; fix the book in the same pull request.
