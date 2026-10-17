---
title: How integrations work
kind: book
order: 13
for: everyone
short: Worlds connects to other things in four ways, and each way has one door and its own rules.
---
"Integration" just means Worlds working with something else. Worlds does
it four ways, and each has exactly one door.

1. **Rooms:** other apps Worlds shows you (Workshop, Engine room, Candy,
   Hive Works).
2. **Providers:** tools Worlds uses for a job, like a chat model.
3. **Sign-in:** your own sign-in service, so one account works everywhere.
4. **Messages in:** anything that wants to tell you something sends a
   notification.

* * *

**One door each means one set of rules each.** Every room is asked the same
questions. Every notification goes through the same door with the same
quiet hours. Every sign-in ends up as the same kind of person inside
Worlds.

That's what makes adding the tenth integration as safe as the first.

* * *

**Worlds never needs another app's code.** It needs the other app to answer
a small agreed set of questions: a contract. The contracts are written down
in public, in Play-Nice, so anyone can build a room.

**Each connection has its own password,** kept in the server's private
settings, never in code, and never shared between connections.

* * *

## Words to know

- **Integration:** Worlds working with something else.
- **Contract:** the agreed questions and answers two programs use. Official terms: *API contract*, *interface*.
- **API:** the doors a program opens for other programs. Official term: *application programming interface*.
- **Adapter:** the small piece that fits a provider into Worlds.
- **Webhook:** one program telling another "something happened". Worlds' room pings are one.

* * *

## Under the hood

Rooms: `room/0` (`rooms.py`, `docs/ROOMS.md`). Providers: the capability registry, and how to add one (`docs/PROVIDERS.md`, `framework validate`). Sign-in: OIDC (`oidc.py`, `auth_routes.py`; groups map to roles through `PW_ROLE_GROUPS`). Messages in: `POST /api/notify` (`push.py`). Play-Nice holds the contracts; Worlds pins the version it follows in `.project/contracts/adoption.yaml`, and CI fails when the pin falls behind.
