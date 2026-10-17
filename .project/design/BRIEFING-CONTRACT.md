# Worlds briefing contract v1 (slice 1b "first light")

> **Superseded in part by [ADR-0008](../../docs/adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

Author: Claude (orchestrator), 2026-09-25. Workers build against this; do not change field names.
Implemented in `src/personal_world/briefing.py` (+ `briefing_voice*.py`, `providers/project_home.py`) and `ui/src/screens/Bridge/`.
Added during 1b: `keeper.greeting` (time-of-day, server clock) and `keeper.name` (display name; the
placeholder owner label "Primary person" is never used). First-visit arrival window is 24h; return
visits count items newer than `since` (max 72h).

## Product intent (read first)
Rylee opens Worlds and her world has already been gathering things. The **briefing** is what her
world knows. The **bridge** is where she explores it. The **Keeper** (the World Keeper, server key
`personal-world`) is how it speaks. Each part of her world has a **resident** (from her own canon)
who reports it in their own voice; personality shapes how information is presented, not decoration.
Honesty is absolute: never invent personal data. When a source is missing or failing, the resident
says so plainly, in character, using the status vocabulary.

## Status vocabulary (existing, src/personal_world/status.py)
healthy · warning · unknown · needs_attention · unavailable · stale · disabled · not_configured

## Systems and residents (fixed for v1)
| system id | display name | resident key | resident name | portrait (served by ui) | source in 1b |
|---|---|---|---|---|---|
| agents    | Workshop     | robot               | Bolt               | /assets/characters/bolt.png          | Project Home snapshot: bookmarks + attention_items |
| estate    | Engine room  | hekek               | Hekek              | /assets/characters/hekek.png         | lab lowbw packet (rows urgent/review/...) |
| records   | Archive      | bruma               | Bruma              | /assets/characters/bruma.png         | the person's journal + pinned records |
| interests | Observatory  | mira                | Mira               | /assets/characters/mira.png          | discovery status (sources/items) |
| news      | Newsstand    | taco-news-truck     | Burrito Journalism | /assets/characters/burrito.png       | media capability (not wired in 1b → honest not_configured) |
| threads   | World tree   | world-tree-squirrel | Ratatoskr          | /assets/characters/ratatoskr.png     | the person's last place + last own journal thread |
The Keeper: resident key `personal-world`, name "Personal World" (the World Keeper), portrait /assets/characters/personal-world.png.

## GET /api/briefing   (require_auth + _require_person; read-only; never writes the journal)
```json
{
  "ok": true,
  "status": "<overall Status>",
  "data": {
    "schema": "worlds-briefing/1",
    "generated_at": "ISO-8601 UTC",
    "since": "ISO-8601 | null",            // previous visit = stored place.updated_at before this visit, else null
    "keeper": {
      "line": "string",                    // 1-2 short sentences, the Keeper's summary in its voice
      "mood": "greeting|calm|busy|sleepy|celebrating",
      "resident": {"key": "personal-world", "name": "Personal World", "portrait": "/assets/characters/personal-world.png"}
    },
    "systems": [ {
      "id": "agents|estate|records|interests|news|threads",
      "name": "string",
      "resident": {"key": "string", "name": "string", "portrait": "string"},
      "status": "<Status>",
      "voice": "string",                   // the resident's one-line report, honest, in character
      "counts": {"arrivals": 0, "have_tos": 0},
      "source": {"name": "string", "observed_at": "ISO|null", "freshness": "fresh|stale|unknown"},
      "items": [ Item ]                    // at most 8 per system, newest first
    } ],
    "have_tos": [ Item ],                  // top 3 across all systems, most important first
    "have_tos_total": 0,
    "arrivals": [ Item ],                  // top 5 across systems, newest first ("arrived while you were away" when since != null)
    "thread": "Item | null"                // the person's own latest journal entry (provenance source == "user"), never a machine line
  }
}
```
Item:
```json
{ "id": "system:stable-id", "system": "agents", "kind": "arrival|have_to|thread|interest",
  "title": "string (<=120 chars)", "detail": "string|null (<=600 chars)", "at": "ISO|null",
  "new": true,                             // at > since (false when since is null)
  "link": {"label": "string", "href": "string|null", "area": "memory|chat|settings|null"} | null }
```
Rules:
- Every source is read with a hard timeout (3s) and failure isolation: one failing source makes only that system `unavailable` (voice says so), never a 500.
- Missing configuration → `not_configured`; an answer older than 24h → `stale`.
- overall status: `needs_attention` if any have_to exists, else worst of systems ignoring not_configured, else healthy.
- The Keeper mood: hour 22-5 → sleepy; any have_tos → busy; arrivals>0 and no have_tos → celebrating; since==null → greeting; else calm.
- No personal data is invented. Counts and titles come only from sources.

## Place (continuity) — "return later and Worlds remembers where you were"
- `GET /api/place` → `{"ok": true, "data": {"place": {"system": "id|null", "item_id": "id|null", "updated_at": "ISO"} | null}}`
- `PUT /api/place` body `{"system": "id|null", "item_id": "id|null"}` (≤2 KB; unknown system → 422) → same shape, stores `updated_at` = now.
- Storage: per-person scoped file `last-place.json` via identity SCOPED_PATH_FILENAMES (model: journal-draft seam, api.py:722-770). require_auth + _require_person, NO step-up, atomic os.replace.
- `since` in the briefing = the stored place's updated_at at request time.

## Source details for 1b
- **agents (Project Home):** provider `providers/project_home.py`. Transport 1 (preferred in dev): CLI at env `PW_PH_CLI` → run `<cli> home --json` (timeout 3s) → JSON schema `ph-home/1` with `attention_items[] {id,kind,project_id,title,detail,source,raised_at,age_min,consequence,action,stale}`, `bookmarks[] {project_id,working_on,next_action,unfinished,updated_at,updated_by}`, `last_sessions[]`, `observed_at`. Transport 2: env `PW_PH_URL` + `PW_PH_TOKEN_ENV` naming an env var holding a bearer token → GET `<url>/api/home` (dict, no envelope; map `attention_items`, and bookmarks may be absent → derive from `projects`/`where_we_left_off` best-effort). Neither set → not_configured.
  - have_tos = attention_items with kind in {owner_decision, tool_failure} (maintenance items → arrivals kind "arrival" only if not stale). Title = title; detail = consequence or detail.
  - arrivals = bookmarks updated in the last 72h, newest first; title = f"{pretty project name}: {first line of working_on}", detail = next_action.
  - pretty project name: strip "proj-" prefix, replace "-" with " ", title-case.
- **estate (lab lowbw):** reuse existing `providers/lab_state.py` (it runs `PW_LAB_CLI lowbw --json`; schema lab-lowbw/1: `overall_state`, `next_action`, `rows` is a DICT keyed urgent/review/safe/unknown/last_known_good/next each with `observations[] {concept, detail, action, evidence}`). have_tos = urgent observations; arrivals = review observations. overall_state UNKNOWN → status unknown.
- **records:** the person's journal (`_state_for`), `thread` = newest event with provenance source "user"; pinned records count via the existing records store if easily reachable, else omit.
- **interests:** existing discovery provider status; zero sources → not_configured; items → kind "interest".
- **news:** not_configured in 1b (voice: honest, in character, "no feed plugged in yet").
- **threads:** the stored place + the `thread` item; status healthy if either exists, else unknown.

## Voice
Module `src/personal_world/briefing_voice.py`: pure functions, no I/O, deterministic.
`resident_line(system_id, status, counts, since_is_set) -> str` and `keeper_line(mood, totals, name_hint=None) -> str`.
Lines come from a table of templates per resident × situation (arrivals / have_tos / quiet / not_configured / unavailable / unknown / stale), 2-4 variants each, chosen by a stable hash of (date, system) so they vary day to day but not per refresh. Voices follow docs/CHARACTER-HANDBOOK.md. Warm, short (≤ 90 chars), never guilt, never urgency theatre, never invented facts; counts are the only numbers used.
