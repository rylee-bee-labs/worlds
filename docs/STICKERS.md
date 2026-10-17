# Stickers: the album every app shares

> **Status:** Current (2026-09-27) · **Canonical for:** Worlds' sticker album and the `stickers/0` shape apps serve · **Read this if:** you're adding stickers to an app, or building the album screen.

**In short:** stickers reward learning, trying and finding things. Each app
keeps its own set and look; Worlds keeps one album per person with a page
per app. About 40% of stickers are open, 30% riddles, 30% secrets.

## Rules every app keeps

- No streaks, day counts or anything that can be lost. Found is forever.
- Nothing from pain, health or medical notes. Finding Rough night is a
  discovery sticker; using it is never counted.
- No leaderboards or comparison, and no late-night bait.
- Stickers land quietly: no push notification, no sound by default.

## Kinds

| kind | Before it's found | After |
| --- | --- | --- |
| `open` | name, picture, how to earn it | the same, marked found |
| `riddle` | only its `riddle`; hidden entirely while its `whisper` neighbour is unfound | name and picture |
| `secret` | never listed; a page says only whether secrets remain | name and picture |

Shine is `paper`, `foil` or `holo` (no rarity percentages).

## An app's set: `GET /room/views/stickers`

The room lists `stickers` in its descriptor's `offers`.

```json
{
  "contract": "stickers/0",
  "app": "vefr",
  "page": { "title": "VEFR", "look": "vefr" },
  "stickers": [
    { "id": "gatekeeper", "name": "Gatekeeper", "kind": "open", "shine": "paper",
      "section": "Making things", "earn": "Lock something behind a key.", "art": "stickers-gatekeeper" },
    { "id": "lantern", "kind": "riddle", "shine": "foil", "whisper": "gatekeeper",
      "riddle": "Some doors only show themselves in the right light.", "art": "stickers-lantern" }
  ],
  "secrets": 4
}
```

Unfound secrets are sent as a count only. `art` names a picture served at
`/room/art/<art>.webp`, which Worlds proxies.

## Reporting a find: `POST /api/stickers/found`

`{app, sticker, context?}`. `context` is a few plain words about where it
happened ("the hidden door with the lantern"), never content. Repeats are
harmless. An app uses its own sticker key (`PW_STICKERS_TOKENS` in Worlds'
private env, `app=token` pairs); that key reaches only this route and only
for its own app. A person may report a Worlds sticker the UI saw them earn.

## The album: `GET /api/stickers`

`{pages: [{app, title, look, stickers: [...], found, shown, secrets_remain}],
unavailable: [{app, error}], total_found}`. Worlds' page comes first, grouped
by `section`. Found stickers carry `name`, `art`, `found_at`, `context` and
`placed`. `POST /api/stickers/place {app, sticker, x, y, r}` saves where a
found sticker sits (x and y from 0 to 1, r from -30 to 30 degrees).

Worlds stickers unlock from saved state when the album is read (lore
confirmed, words found, the Later shelf, rooms visited, a corrected journal
entry), from a few moments as they happen (Remember, answering or undoing a
card, starting a riff, unlocking the vault), or from the UI (a tap on Sol,
finding Rough night). Art: `/assets/stickers/<id>.webp`.
