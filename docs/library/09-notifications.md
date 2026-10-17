---
title: Notifications
kind: book
order: 9
for: everyone
short: Worlds can reach your phone, but it stays quiet unless you say otherwise.
---
Worlds can reach your phone, but it tries hard not to be loud.

Every notification has a **tier**: good news, an update, or "when you're
ready". You choose which tiers may buzz. By default only good news does;
everything is still kept in the list inside Worlds.

* * *

**Quiet hours** are on by default, 21:00 to 08:00. During them nothing
buzzes; notifications still arrive, and you get one summary when quiet
hours end. The "Send me a test" button always goes straight through.

**Private:** an app can mark a note private. Then the Lock Screen shows no
title and only a plain message, and the details wait inside Worlds.

* * *

**On iPhone,** notifications only work through the installed app: in
Safari, Share, then Add to Home Screen, then open Worlds from that icon
(iOS 16.4 or newer).

Anything can publish: a room, a script, you. They all go through one door,
so the same rules apply to every sender.

* * *

## Words to know

- **Tier:** how loud a notification is: good news, an update, or "when you're ready".
- **Quiet hours:** the hours nothing buzzes (21:00 to 08:00 by default).
- **Push:** a message that arrives even when the app is closed. Official term: *Web Push*.
- **VAPID key:** the key pair that proves notifications really come from your Worlds.
- **PWA:** a website installed like an app. Official term: *Progressive Web App*.

* * *

## Under the hood

Publish through `POST /api/notify` (people, or agent tokens with the `notify` scope). The service worker is `/sw.js`: it shows pushes and opens links, and never caches. Keys come from `PW_VAPID_PRIVATE_KEY` and `PW_VAPID_SUBJECT`. History is kept 90 days. Code: `src/personal_world/push.py`. Canonical: `docs/NOTIFICATIONS.md`.
