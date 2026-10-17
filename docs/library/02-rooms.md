---
title: Rooms
kind: book
order: 2
for: everyone
short: A room is another app that Worlds can show you and pass your answers back to.
---
A room is any app that speaks one small language, the **room contract**:
five questions Worlds can ask it.

- **Who are you, and are you well?**
- **What's new?** Cards.
- **What needs a person?** Needs.
- **What can I ask you to do?** Actions.
- **Please do this.** One action.

* * *

Any app that answers those doors can be a room. Worlds learns the list of
rooms at runtime from the Workshop, so adding a room needs no Worlds release.

Every room has its own token (a password for Worlds to use). The token lives
in the server's private settings, never in the code.

* * *

**The room owns its data.** When you answer something in Worlds, Worlds
passes your answer to the room, and the room decides. The room writes a
**receipt**, and only the receipt says whether anything changed. Worlds
never says "done" on a room's behalf.

**Every action carries a key** (an idempotency key). If your phone sends the
same tap twice, the room does it once.

* * *

**Links open on the room's own site, never through Worlds.** A pass-through
would hand every room your Worlds sign-in.

The one exception is pictures: an image can't carry the room's token, so
Worlds passes a room's pictures through itself. It lets only real image
files through (it checks their first bytes), never a page or a script.

* * *

**One way to answer.** A need can offer up to six choices, and sometimes
room for your own words. Worlds answers every need the same way; the room
routes the answer to the right place. Learned the hard way: when each kind
of need had its own action, a Merge tap went to the wrong one and was
quietly refused.

* * *

## Words to know

- **Contract:** an agreed set of questions an app must answer. Rooms use `room/0` from Play-Nice.
- **Token:** a password one program uses to talk to another. Official term: *bearer token*.
- **Receipt:** the room's own answer to "did that work?".
- **Idempotency key:** a label on each tap so a repeated tap only counts once.
- **Proxy:** a middleman that fetches something for you. Worlds refuses to be one for pages, on purpose.

* * *

## Under the hood

The five doors: `GET /room`, `GET /room/cards`, `GET /room/needs-you`, `GET /room/actions`, `POST /room/actions/{id}` (with an `Idempotency-Key` header). The room list comes from the Workshop's registry (`PW_ROOMS_REGISTRY_URL`), cached 60 s with a last-known-good copy. Tokens live in the server's environment under names like `PW_ROOM_WORKSHOP_TOKEN`. Pictures pass through `GET /api/rooms/{id}/art/{name}.webp` (WebP only, checked by its first bytes). Answers go through `answer-decision` with `{need, choice}` or `{need, text}`. Code: `src/personal_world/rooms.py`. Canonical doc: `docs/ROOMS.md`.
