---
title: Live, both ways
kind: book
order: 3
for: everyone
short: When an app changes, it tells Worlds, and your open screens update within seconds.
---
Worlds used to ask each room "anything new?" every so often. That works, but
it's slow and wasteful, and a screen you're looking at could be a minute
behind.

Now it's two-way.

* * *

**From a room to Worlds:** when a room's data changes, it pings Worlds:
"hive-works changed". The ping carries no content, so the worst a wrong
ping can do is make Worlds look again.

Worlds forgets what it remembered about that room, and tells every open
screen through a live stream. The screens re-read the room within seconds.

* * *

**From Worlds to a room:** what you do in Worlds (answer, merge, riff) goes
to the room as an action. When the room says it worked, Worlds tells the
open screens on your other devices too.

* * *

If the live stream drops, the browser reconnects by itself, and the regular
refresh still runs underneath. Live is a speed-up, never the only way to be
right.

* * *

## Words to know

- **Polling:** asking "anything new?" on a timer.
- **Ping:** a tiny "I changed" message with nothing else in it. Official term: *webhook*.
- **Live stream:** a connection the server keeps open to push news to your screen. Official term: *Server-Sent Events (SSE)*.
- **Cache:** a short-term memory of an answer, so Worlds doesn't ask again every second.

* * *

## Under the hood

A room pings `POST /api/rooms/{id}/changed` (an agent token with the `notify` scope). Pings less than 2 s apart fold into one. Open screens listen on `GET /api/rooms/events` (event `room-changed`, data `{room, at}`, a heartbeat comment every 20 s). The UI hook is `useRoomEvents()`, which refreshes every query under `["rooms"]`. Read-only room views: `GET /api/rooms/{id}/views/{name}[/{item}]`, 15 s cache, cleared by a ping. Code: `rooms.py` (`room_changed`, `listen`, `view`).
