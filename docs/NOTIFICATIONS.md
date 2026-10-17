# Notifications — Web Push, in plain words

> **Superseded in part by [ADR-0008](adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../FRONTEND-INVENTORY.md).

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** how Worlds sends notifications (VAPID keys, the API doors, the Settings screen, iPhone) · **Read this if:** you want notifications on your phone, or you run a World and need to switch the whole thing on.

**In short:** Worlds is the notification hub. Your browser's own push
service (Apple's, Google's, Mozilla's) carries a short message to your
phone — no Firebase, no ntfy, no third-party account. A person turns it
on in **Settings → Notifications**, one device at a time. The person who
runs the World turns it on for the server once, with two environment
lines. Everything here works or fails honestly: with no key set, push
says `not_configured` and the rest of Worlds is untouched.

*Sanitized: `<worlds-host>` and `mailto:you@example.invalid` are
placeholders — substitute your own values.*

## Front-door app (current implementation)

**Status:** Web Push and its PWA shell are wired into the front-door app. With no VAPID configuration, the UI reports **not configured**; this does not mean a push delivery has been verified. The deployment remains a skeleton while Home is built.

### Where the parts live

- `src/personal_world/push.py` owns storage, VAPID, preferences, deduplication and delivery.
- `src/personal_world/worlds/push_routes.py` owns the new app's notification API; `production.py` assembles it.
- `src/personal_world/worlds/static_routes.py` serves the built SPA and root-scoped PWA files.
- `ui/public/sw.js`, `manifest.webmanifest` and the icons are the PWA assets.
- `ui/src/fd/Notifications.tsx` is the Settings device setup surface.

Project Home publishes to `POST /api/notify`. An owner creates an agent token through `POST /api/agent-tokens` with scope `notify`; the token is shown once and must be kept secret. The agent sends `Authorization: Bearer <token>`. Each publish targets the one owner, has no `to` field, and should set `dedupe_key` to the Project Home need id. A saved notification is recorded even when push is not configured.

## The two keys (server side, once)

Push messages are signed with a VAPID key pair. Generate one:

```bash
personal-world push keygen
```

It prints a private key (a PEM block, or pass `--json` for a base64url
one-liner) and its public counterpart. The private key goes into the
server's environment; the public key is served to browsers automatically
at `GET /api/push/public-key` — you never paste it anywhere.

```bash
PW_VAPID_PRIVATE_KEY="<the private key that keygen printed, as one line>"
PW_VAPID_SUBJECT="mailto:you@example.invalid"   # a contact the push services may use
```

Both lines are optional. With them unset, every notification still
stores and every screen still works; nothing pushes, and the state reads
`not_configured`. The private key is never logged, never sent in an API
response, never written to disk by the app — `env.example` explains the
same in one comment block.

Push needs HTTPS: browsers only allow it on `https://` or on
`localhost`. See [INGRESS-AND-TLS.md](INGRESS-AND-TLS.md) for the proxy
pattern.

## Getting it on a phone (a person, per device)

1. Open `https://<worlds-host>/` and sign in.
2. Go to **Settings → Notifications**. The first line tells you the
   truth in words: not configured / off / on / blocked.
3. Press **Turn on for this device** and allow the browser's prompt.
   This button is the only place the app ever asks.
4. The device appears in the list below (a label like "iPhone" and
   delivery times — never its keys or endpoint), and it can be removed
   again.

On iPhone, notifications only work through an installed app. Safari
notices and shows the directions instead of a button that cannot work:

> To get notifications on iPhone, add Worlds to your Home Screen: Share,
> then Add to Home Screen, then open it from there.

(That needs iOS 16.4 or newer.) Open the Home Screen icon, sign in, and
press **Turn on for this device** there.

**Send me a test** goes out straight away, even during quiet hours (you
just pressed it). It says "Test sent" when a device was pushed to, or
that nothing is subscribed yet.

## What reaches you, and when

Settings → Notifications also holds the three dials:

- **What reaches you** — the three tiers, each on or off:
  - `GOOD NEWS` (`good_news`) — things worth a look right away;
  - `A SMALL UPDATE` (`update`) — day-to-day happenings, reminders included;
  - `WHEN YOU'RE READY` (`when_ready`) — things for later.
  Only GOOD NEWS pushes by default; the other two are stored in history
  until you switch them on. A source you switch off is kept in history only.
- **Private** — a publisher can send `"private": true`: the Lock Screen then
  shows only the sender and "Open Worlds to read it."; the words are in
  history.
- **Quiet hours** — on by default, 21:00 to 08:00. During quiet hours
  nothing buzzes; notifications still store, and when quiet ends one
  short summary arrives ("N things waited for you").
- **History** — every notification is stored before anything is pushed,
  and kept for 90 days.
  `GET /api/notifications?unread=1&limit=20`, `POST
  /api/notifications/{id}/read`, `POST /api/notifications/read-all`.

Dead devices tidy themselves: when a push service answers 404 or 410
(the subscription is gone), Worlds drops that device from the list; any
other failure keeps it and shows the plain-words reason on the row.

## The door for scripts and agents: `/api/notify`

From a cron job, a companion, or any other server-side friend:

```bash
curl -s https://<worlds-host>/api/notify \
  -H "Authorization: Bearer $PW_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tier": "good_news", "source": "garden", "title": "The tomatoes ripened", "body": "Six of them, all at once.", "link": "/memory"}'
```

The answer is small and honest: `{"id": …, "delivered": …, "deferred":
…, "state": "delivered|no_devices|not_configured|deferred"}`. Rules:

- `tier` must be one of the three names; `source` is a plain word
  (letters, digits, `_`, `-`, `:`); `link` must be a same-origin path
  like `/memory` — anything offsite is refused.
- A person's token notifies that person. An agent (service) token needs
  the `notify` scope and lands in the owner's history; it may name
  another person with `to` only if the owner granted `manage_people`.
- 30 notifications a minute per caller, then a plain `429` ("wait a
  moment"). Same `dedupe_key` within 24 hours = the second call is
  stored once and answers `duplicate` — safe to retry.

The same door as a command:

```bash
PW_API_TOKEN=… personal-world notify \
  --tier update --source reminders --title "Pick up the yarn" \
  --body "It has been three weeks." --link /memory --dedupe-key yarn-2026-09-26
```

(An agent service token with the `notify` scope works the same way;
reminders inside Worlds use this same push path.)

## Operator to-do (by hand, once)

1. `personal-world push keygen`, put the private key and a
   `mailto:`/`https:` subject into the server's environment
   (`PW_VAPID_PRIVATE_KEY`, `PW_VAPID_SUBJECT`), restart.
2. Confirm HTTPS: `curl -sI https://<worlds-host>/api/push/public-key`
   answers 200 (409 means the key did not take).
3. On each phone/laptop, open the World and press **Turn on for this
   device** once (on iPhone: from the Home Screen install).
4. Press **Send me a test** and expect a buzz.

## Where the parts live

- `src/personal_world/push.py` — hub, stores, quiet-hours clock, the one
  `pywebpush` call site.
- `src/personal_world/api.py` — the `/api/push/*`, `/api/notifications*`
  and `/api/notify` doors, and `/sw.js` served at site root.
- `ui/public/sw.js` — the service worker: shows the notification, opens
  the link when tapped; it caches no fetches.
- `ui/src/data/push-client.ts` + `ui/src/screens/Settings/Notifications.tsx`
  — the device half and the Settings screen.
- `tests/test_push.py` — the behavior above, proven against a mocked
  push service.
