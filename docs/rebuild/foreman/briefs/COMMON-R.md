# Common rules for every recipe worker

You are drafting sanitized C1 config templates ("recipes") for homelab services, plus recorded sample responses and tests data. Read first: `src/personal_world/worlds/models.py` (the C1 models), `docs/rebuild/CONTRACTS.md` (C1, C1.3), `src/personal_world/worlds/recipes.py`, `tests/recipes/test_recipes.py` (the harness your files must satisfy) and `src/personal_world/worlds/seed.py` (a worked example of provider, request and card objects).

Layout per recipe, all under `config/recipes/<recipe>/`:
- `recipe.yaml`: `schema_version: 1`, `name` (= directory), `title`, `summary` (one plain sentence), `status: ready`, `note: ""`, `env: [NAMES]` (the secret names the provider reads).
- `provider.yaml`: `schema_version: 1`, `id` (= recipe name), `name`, `kind: http`, `base_url: http://<service>.lan.example:<port>` (placeholder, exactly this shape), `auth: {type: header, header_name: X-Api-Key, secret_ref: env:<NAME>}` (or `type: none` where the brief says no auth), `network: {lan: true}`, `timeout_s: 5`, `max_bytes: 1048576`.
- `requests/<name>.yaml`: `id: <recipe>.<name>`, `provider: <recipe>`, `method: GET`, `path`, `query` (strings; `{today}` / `{today+7d}` templates allowed in query values only), `effect: read`, `ttl_s` (60 to 300), optional `assertions`.
- `cards/<card-id>.yaml`: `id`, `title` (plain: "TV", not the product name), `icon` (a simple word: tv, film, music, book, download, search, subtitles, broom, hound, heart, drift, key, route), `group` (life or machine), `request` or `requests`, `view`, `meaning: {concept, short, full}` (plain, sparse, no jargon), `fields` (each `path`, `label`, `format`, `unit`), optional `meter`, optional `status`.
- When a card lists several `requests`, its fields read `$.<request-name>...` (the part of the request id after the dot).

Samples, in `tests/recipes/samples/<recipe>.yaml`: `cards: {<card-id>: [cases]}`. Every card needs at least these cases, each `{name, responses: {<request-name>: <JSON body>}, expect: {state, values: {<field-key>: "<text>"}}}`:
- a normal case (state `healthy`, or `needs_attention` where the rules say so) with realistic, SANITIZED bodies (made-up titles like "Example Show"; no real names);
- an `unavailable` case: `responses: {<request-name>: {__status: 500}}`;
- an empty or edge case where the service can return nothing.
The field key is the slug of its label ("Next episode" becomes `next-episode`; a collision gets `-2`). Expected `text` is exactly what the engine prints (run the test to see it), never guessed.

Hard rules:
- Only the placeholder host shape above. Never a real hostname, domain, IP, tracker, topic, tag or personal name. No credentials. Secret refs are `env:NAME` only.
- Every request is a GET with `effect: read`. The only exception is a write request an action points at (the Sonarr brief says which).
- Missing is never 0. Do not invent progress. Use only the JSONPath subset (`$.a.b`, `[n]`, `[-1]`, `[*]`), the formats (number, percent, bytes, duration, relative_time, text, count) and the status map options (`mode first|all|any`, `empty unknown|healthy`).
- If you are not sure of an endpoint or a response shape, put the doubt in the recipe's `note` field as plain text (for example "Endpoint shape assumed from the Readarr API; not yet checked against a live instance"). Never put doubts in a card's `meaning` (that text is shown to the owner), and never fake a field.
- If a test contradicts a brief, stop and report; never edit `tests/recipes/test_recipes.py` or any other test, and never weaken a check.

Acceptance is in your brief. Run it before you finish and report its last lines verbatim.
