# HANDOFF — UIX / USABILITY PASS (IN PROGRESS → PICK-UP POINT)

**Date:** 2026-09-17
**Lane:** product-usability review of the Station UI (`design/opendesign-exploration/station/`, served same-origin at `/station/`)
**Status:** Source-walk of the ENTIRE Station UI is complete. No fixes committed yet — deliberately. The half-finished blocker is the live-browser walkthrough; Rylee is taking that over and handing the file back.

---

## State of this lane

- **Read:** all 13 Station JS files (~5.9k lines), all HTML pages (index, chat, journal, projects, interests, settings), `station.css` (tokens, low-demand, help dialog), `mobile.css`, login page (`login_page.py` rendered HTML), plus `HANDOFF-UI-FIX.md`, `STATION-NAVIGATION-MODEL.md`, `STATION-DOMAIN-MAP.md`, e2e specs (`station-honest-states`, `station-a11y`, etc.), `e2e/server.mjs`.
- **All 13 JS files pass `node --check`** — no syntax rot; the earlier "ariaible" grep hit was a false positive of my own pattern.
- **Do NOT touch these dirty files** (another lane's work): `src/personal_world/identity.py`, `src/personal_world/providers/adapters.py`, `tests/test_identity.py`. Stage explicit paths only; never `git add -A`.

## Blocker at hand-off

Dev instance at `http://127.0.0.1:8000` (up, `personal-world-core-1`) serves `/login` correctly but `/api/auth/login` rejects the container's own `PW_API_TOKEN` (401). Container is 10h old; local `identity.py` is modified by another lane — likely a token/identity-store mismatch, or the container predates the change. **Not diagnosed.** Two paths, pick one:

1. **Recommended:** use the sanctioned e2e test server — `node frontend/e2e/server.mjs` boots the real FastAPI app on `:8731` with a fresh temp world (setup-complete, `ci-token` bearer, zero proposals/reminders — perfect for the honest-empty-state walkthrough). Login in browser with token `ci-token`. It is the same app the Playwright gates use.
2. Or restart `personal-world-core-1` / fix its login to test the actual dev world instead (world has one fact: "Rylee's Place"; harmless either way).

Dev-bypass note: `PW_DEV_AUTH_BYPASS` is opt-in and OFF here by default; the login page has SSO-primary + collapsed access-code fallback and is quite polished.

---

## Findings so far (RELEASED FROM SOURCE WALK — mark implemented: no, until fixed)

### P1

| ID | Screen | Finding | Smallest fix |
|---|---|---|---|
| UX-01 | Chat (`chat.js`) | Sending a message just inserts a **fake system line** "`X heard you. Replies bind to the real chat capability (API-010) — nothing is invented here.`" — reads like a dev note, repeats every send, and gives no recovery/instruction. Also no loading/error/provider states; if the real chat API exists (`chat.py`, `API-010..012`) it is not wired. | Bind send to the real chat API; if genuinely unwired, show the honest "not connected yet" state ONCE in the room, not per message, and drop "API-010" jargon from the surface. |
| UX-02 | Journal | **Three journals on one page**: real API-005 panel ("Your journal"), a fully redundant specimen `journal-view.js` panel ("Journal entries · specimen view" whose intro even says "No journal is connected yet" — stale), and a localStorage tab solec "Your words" writing to `pw-journal-entries` on-device only. A tired user cannot tell which is the real one; the Write tab saves to localStorage while the API (`API-006 POST /api/journal`) exists. | Remove the specimen view panel entirely; wire the Write form to API-006; fold the real panel and Your words into one journal. |
| UX-03 | Journal localStorage entries | "Saved on this device. Nothing leaves unless you say so." — a one-line entry vanishes with browser data and is invisible to the API/world; that honest sentence is not enough to prevent silent loss. | Write entries via API-006 (real journal) as the fix; until then move the localStorage writer behind the same disclosure as specimen data. |
| UX-04 | Settings | Controls write **localStorage only** while a `API-030 PUT /api/prefs` + schema exist; the page honestly says so in a binding table, but THREE copies of truth (server prefs, station prefs, per-page controls) pressure the user's trust: "Is my setting in the world or just this browser?" | Small, correct step: bind density/motion to `API-030` values on load, PUT on change (step-up already documented in the same table); keep non-server-only prefs (mood/theme) device-only. Defer a full preference-intent regroup. |
| UX-05 | Settings | Every settings group carries a full "chat says:" panel that re-explains the same three toggles above it — the companion voice has become the page's second narrator. Cutting any 1 of 4 does not hurt the product; the copy contradicts sections' one-line descriptions by rephrasing them at length. | Keep ONE companion tip total (highest-value one, e.g. motion); drop the rest. The voice stays in Chat and the corner orb. |
| UX-06 | Login | Access-code fallback leaks implementation shape onto the calm surface: "The access code belongs to this world and is set by whoever runs it" is good; but `503 → "Sign-in is not set up on this instance yet."` next to the current `pw_auth_error` mapping says plain "Sign-in is not configured correctly on this instance" — P2-grade wording (unclear next step) and it does not tell WHO to ask. (This one is probably already fine in practice since it's server-rendered; verify on :8731.) | Tiny copy change: "This instance's sign-in is not set up yet. The person who runs it can enable it in setup." Verify (UNVERIFIED — needs the :8731 walkthrough). |
| UX-07 | Topbar naming | Three topbar affordances say conflicting names for help: injected button = "Hail Assistant", settings copy references "I need help" (topbar) **and** "Hail Assistant", nav model doc says fixed **bottom-left**. The component is in the topbar, not bottom-left. Naming collapse into one term. | Pick "Hail Assistant" (already rendered) or "I need help", change the other two references + `aria-label` consistency. |
| UX-08 | Help dialog | `data-help="restore"` in `station.js` **silently re-enables ambient motion** (`motion='off'`→`''` default) along with demand-normal on "Bring my world back". Someone with reduced-motion needs who clicked "Make everything quieter" then "Bring my world back" gets motion back ON without asking. That's an accessibility contract violation (OS pref must win — verified it does win, but the application pref flip is still unnecessary). | Make "Bring my world back" restore demand only, never touch motion. |
| UX-09 | Station index | In low-demand mode, the map (`.sky`) is hidden, but the **Still-served "Needs you" section below the quiet block keeps the FULL panel** (duplicate heading "needs you", duplicate chip, full item list, and specimen tech disclosure) even in quiet mode since the second `data-rd-needs-you` mount isn't `data-rd-variant="quiet"`-toggled — check on :8731 whether the section below the quiet-block is actually hidden in low demand or stubbornly visible. UNVERIFIED from CSS alone (`[data-demand="low"] .sky { display:none }` hides the sky and `.notices`, but the Needs-you `<section>` has class `block`, not `.notices`) — so low demand shows TWO needs-you panels (quiet summary + full list) instead of one. | Give the Needs-you section the demand-aware treatment (either `notices` class or hide `.block[data-labelled-by="h-needs"]` under `[data-demand="low"]`), since the quiet variant already carries the same truth. |

### P2

| ID | Screen | Finding | Smallest fix |
|---|---|---|---|
| UX-10 | Projects | Page is functionally a **git-state debug dump labelled as a product**: five entirely SPECIMEN repositories, the panel even shows unrelated repos (`lantern-notes`, `pickle`, `old-notebooks`) that are not Rylee's. Real wiring exists (API-079/033/034) and is documented but **not wired**. Ordinary use = confusing fiction; needs real data behind specimen removal once reads are bound. | Wire the real reads (`API-079 status` + `API-033 per-repo`) into the existing shape (the code itself says "swap later"); until that lands, the page should default to an honest "not wired yet" state instead of five fake repos. Stop render of specimen repos during daily use. |
| UX-11 | Projects | "Propose refresh" gate is a 6-step essay including API numbers and "not wired in this prototype" — this is in the primary surface of a page whose product intent is "project first, git state second". | Collapse the gate to 1–2 steps shown + "more about the flow" disclosure that carries the rest. |
| UX-12 | Interests | Duplicate interest-management surfaces: [a] curated **specimen** `interests-view.js` "Discoveries" panel (keep/dismiss that only mutates page-load state), [b] fully-local add/remove Music/AI/Reading triple-grid with editable localStorage only. Neither is called "specimen" loudly enough given #b LOOKS like the managed content and #a LOOKS like the recommendation feed. A tired user can genuinely not tell which list is theirs and why one says "added $" / "source · API-052" gibberish. | Give the specimen feed an honest permanent header ("This panel is a design preview, not your interests") displayed outside the technical disclosure, and wire the interest grid to API-051 or to an honest "not wired" state as the primary surface. |
| UX-13 | Interests (tags) | Cards carry literal placeholders in the map/starmap data: `'[ an item ] · source · API-052 · when'` literal placeholder brackets with the string `when` rendered as a word. Clearly leaked drafts. On map dive panels too: `"activity: specimen: an album you returned to 4x"` and `From API-051 · API-056` — polished content that still API-crumb-talks to tired eyes. | Replace the placeholder objects in starmap.js with one concrete honest sentence per cluster (e.g. "nothing here yet — real data waits on API-051"), e.g. copy the spec's language `not set up yet`. |
| UX-14 | Starmap `/ Settings / index` | The info strip (`Currently / From / Suggests / Needs-you-here`) states "specimen:" prefixes rendered on EVERY line on every page — the word "specimen" appears 10+ times on the Observation Deck; it stops being information and becomes noise on the calm viewport, undoing the low-noise goal. | Once per page max, in one dismissible line ("sample data, marked ✓") OR keep the technical disclosure vocabulary but delete the leading "specimen:" prefix from the info strip and rely on the map-note under the map that already explains the honesty rule. |
| UX-15 | Station.js help dialog | The "Bring my world back" action **restores motion** too (see UX-08) AND “restore” in the follow-up sheet reads as data-restore; there's no distinction between restoring state and restoring view… the copy is fair but the motion flip is wrong (that's UX-08). Skip; folded into UX-08. | — |
| UX-16 | Settings "Your data" | "Clear journal entries" only clears the **localStorage** solec; the real server journal (`API-005` entries rendered directly above this panel's text) is untouched, yet the button is silent about that gap. Real journal entries will outlive the clear and the user will think the clear applied. | Re-label each destructive button to its true scope ("Clear device journal (local notes only)") and add "Journal on the server is managed on the real journal page." |
| UX-17 | Chat templates | Template selection sets `input.value` = prompt text — the *visible experience* is "I clicked a template and now it's a normal typed message, personality label persists" — fine. BUT there is **no template for "just talk"** in the card row, only in the head-line ("Pick a mood, or just talk") — and selecting a mood is a separate concept from the personas. One chip "Just talk ✦" clear the template state. | Add a "Just talk" card as the first chip per companion. |
| UX-18 | Chat damping | Every send appends a system line after the user's own message without ever addressing what was said. Each send = a promise the reply won't be invented, in robot legal language, repeated forever. Pillastre the system line, then the room reads as an actual dead chat. | Same fix family as UX-01; the surface-level part (remove `— nothing is invented here` system line, keep one honest room-level banner). |
| UX-19 | Journal tabs | The `role="tablist"` in `.journal-tabs` lacks keyboard arrow-key pattern (required by WAI-ARIA tab pattern: Left/Right/Up/Down activation). Tabs currently only respond to focus+Enter/Space. Not a blocker; fix in the journal consolidation (UX-02) rather than alone. | Add arrow-key handling in the same consolidation patch. |
| UX-20 | Settings "How it looks" | Setting labels are excellent ("Space between things", "Colours", "Let the map set the mood") — **do not change.** But the垄断 layout puts two competing affordances for the same setting on one panel: a segment control AND a companion "says:" action button strip — your eye has to figure out which one "wins" (both write the same localStorage — one via chat-action JS, one via `data-*-set`). | Remove the companion action strip (folded from UX-05); the segment buttons above are the single real control. |
| UX-21 | Chat page copy | "A companion travels with you on every page — the glowing orb in the corner is this same door." is warm, but the page `chat.html` also ends with: "Companions are presentation, never a dependency: everything here works with them off." — a good line but it is the THIRD honesty note on the screen (title lede + empty-state honesty + deck-exit bottom line). One is enough. | Cut the deck-exit bottom line (or move it behind the technical disclosure). |

### P3 (polish)

| ID | Screen | Finding | Smallest fix |
|---|---|---|---|
| UX-22 | Index footer | Mapping-div div `<p class="map-note">` under the map says "A world that has grown a little and wears a soft ring has things inside asking for you" — genuinely lovely, keep. |
| UX-23 | Settings | Clear interest/journal/chat/positions buttons say "**Clear**" but nothing prevents double-click-period accidents inside a single confirm dialog; the confirm copy itself is honest. Fine to leave. |
| UX-24 | Deeplink | Weakness: `restore()` in deeplink.js runs `zoomOutToGalaxy()` then clicks each segment — with a custom-hidden/renamed node the drill is silently truncated. Edge case; not a fix now. |
| UX-25 | Starmap ambient egg | Fires once per session at 45s. `sessionStorage` + `companions=off` + reduced-motion are all respected. Good — no fix. |
| UX-26 | Search | `score()` ranks overview for terms like `map|home|overview|start|world|seven|top` — good. No fix. |
| UX-27 | Onboarding | "You can replay this any time from 'Show me again' in the top bar" is in the dialog footer but the topbar button is only injected on pages with `.topbar` — fine everywhere except any future page without a topbar. No fix. |
| UX-28 | Low-demand CSS | `[data-demand="low"] body { font-size: calc(var(--fs-body) + 1px); }` bumps base font — nice, and never drops below 44px, matches contract. No fix. |

## What already works especially well (DO NOT TOUCH)

- The **Observation Deck / seven-constellation rest state** and complexity-on-demand drill model (`starmap.js`) works and reads beautifully; the "needs you" copy in `aria-label` + info-strip redundancy is textbook for the a11y contract.
- **Honest-states engine** (`real-data.js` + the shared `needsYou()` fetch across low-demand + normal mounts) is genuinely good — "Nothing needs you right now. Both sources were checked just now — this is verified, not assumed" is exactly the product voice, and it refuses to say "all quiet" without both sources answering.
- **Login page** (server-rendered `login_page.py`): passkey-first SSO block, collapsed fallback, honest per-error mapping, `role=alert`, polite live region, focus restoration, reduced-motion kill, skip-link, 44/48px targets. Best thing in the repo.
- **Backup/restore panel** (`backup-ui.js`): 44px floors, passphrase never persisted, honest 404/501 "not wired in this build" states, real per-file restore report, `prefers-reduced-motion` honored — a fully designed component, not a stub.
- **Search palette** (`search.js`): real ARIA 1.2 combobox, `activedescendant`, focus trap, reduced-motion aware.
- **Skip-link, backdrop-inert onboarding dialog, focus trap + focus return** in `onboarding.js` — solid.
- **"Shape this map" editor** (`shapemap.js`) — user-malleable structure as a patch, and the search/deeplink/integration respects it.
- Playwright gate suite already covers: axe-with-contrast (serious/critical = 0), 44px audit, no-fake-strings gate (`no-fake-strings.py` elsewhere) for specimen leakage to non-technical surfaces, keyboard, honest states, motion + reflow. **These are the regression checks any fix must respect.**

---

## Pick-up point (exact next action for the next agent)

1. Boot the e2e server: `node frontend/e2e/server.mjs &` (real app on `127.0.0.1:8731`, login with token `ci-token`), then drive `/station/` with a real browser.
2. Verify-by-eye the UNVERIFIED findings: UX-06 (login copy), UX-09 (double Needs-you in low demand), UX-12 (does Discoveries panel read as fake to a tired eye), UX-11 (gate essay length), UX-14 (specimen-word fatigue).
3. Commit small fixes only, in separate commits, staged by explicit path `design/opendesign-exploration/station/<file>`. Suggested comfortable first batch (small, clearly correct):
   - UX-08 (help dialog flips motion back on along with demand)
   - UX-07 (naming collapse "Hail Assistant" vs "I need help")
   - UX-14 (delete the "specimen:" prefix in the info strip; keep one on-page honesty line)
   - UX-13 (caption the placeholder `[ an item ]` copy inside starmap.js cluster objects into honest plain-language lines)
   - UX-16 (relabel "Clear journal entries" → "Clear device journal (localStorage notes only)")
4. Then run the regression lanes after each batch: `cd frontend && npm run test:e2e` (spec files `station-*.spec.ts`) and confirm all green before each commit.
5. The **larger, product-decision fixes** (UX-01 chat wiring, UX-02/03 journal consolidation via API-006, UX-10 projects wiring via API-079, UX-04 settings binding to API-030, UX-12 interests wiring via API-051) are NOT mechanical: they change what data the product honestly presents. Each needs Rylee's product-taste call, and during the same lane the topics genuinely deserve a dedicated `personal-world` route since they are reachable features, not sample shops.

## Validated environment notes (for whoever picks this up)

- Product: FastAPI core, container `personal-world-core-1` on `:8000` (dev mount; `scripts/dev.sh`). `/station/ → /login` works; `/login` renders from `login_page.py`.
- e2e server boot: `node frontend/e2e/server.mjs` at `:8731`, fresh tmpdir world, `PW_API_TOKEN=ci-token` bearer + `/api/auth/login` mints a session cookie.
- The world's stored accessibility prefs from the dev data are already non-default (`motion: subtle, contrast: comfortable, text_scale: 1.25, density: compact, target_size: 56`) — the **server-side** values may not match the **Station-side** localStorage values rendered by the same page, which is exactly the UX-04 trust gap.
- The `PW_API_TOKEN` in the container env does not pass `/api/auth/login` today. Working diagnosis path: `docker exec personal-world-core-1 printenv PW_API_TOKEN | xxd | head` vs `/data/sessions.json` (hash-token store) — do NOT print the token into agent output or shell history beyond the first four characters. This credential is not in any tracked file (checked; and `tests/test_public_safety.py` is the gate).

---

## Verification — live walkthrough, 2026-09-17 (this lane)

Environment: `node frontend/e2e/server.mjs` on `127.0.0.1:8731`, fresh seeded
world, login `ci-token`, real Chromium via the repo's Playwright deps.
Screenshots in /tmp (not committed). No page errors observed on any page.

| ID | Verdict | Evidence |
|---|---|---|
| UX-06 | **verified, partially already-better** | Server-rendered `src/personal_world/static/login/index.html`: the 503 path already says "Sign-in is not set up on this instance yet." (matches the suggested copy). Remaining gap: the `oidc_misconfigured` mapping still says "Sign-in is not configured correctly on this instance." with no "who to ask". Suggested: "Sign-in is not set up on this instance yet. Whoever runs it can finish setting it up." — NOT committed (outside the small batch). |
| UX-09 | **verified** | Low demand (help → "Show me only what needs me"): BOTH needs-you mounts visible — `data-rd-variant="quiet"` AND the full mount — rendering duplicate "Needs you"/"NEEDS YOU" headings, duplicate chips, duplicate copy, and the tech disclosure (screenshot, fullPage). The fix from the handoff's table (demand-aware treatment of the Needs-you section) is still needed. UNFIXED — it is mechanical but was outside this lane's named commit batch. |
| UX-11 | **superseded (mostly)** | The 6-step essay (gate panel) is NOT on the primary surface; `.pv-gate-panel` starts `hidden` and opens only on deliberate "Propose refresh" click. Primary surface shows a 1-paragraph lede + a labelled button. Progressive disclosure already satisfied; no change made. |
| UX-12 | **verified (mitigated)** | Interests page (reachable directly; nav entry hidden in seeded world) shows "Discoveries / SPECIMEN VIEW" — the preview header IS permanently displayed outside the technical disclosure and honestly explained. Wiring to API-051 remains owner-decision. |
| UX-14 | **verified (less severe on index; worse on interests)** | Observation Deck galaxy view: only 2 "specimen" occurrences in main text. Interests dive region: 10 occurrences (info strip + Discoveries) — fatigue confirmed. |
| UX-13 surface | **verified** | `'[ an item ] · source · API-052 · when'` literal placeholders rendered verbatim in dive lists. FIXED this lane. |

**Committed this lane (small, clearly-correct batch, all verified above and via
`npx playwright test` regreen):**

- UX-08 — `station.js`: help "restore" resets demand only; motion preference never silently re-enabled.
- UX-07 — one name, "Hail Assistant": settings.html "I need help" reference, station.js bottom-left comment, STATION-NAVIGATION-MODEL.md location line (component lives in the topbar).
- UX-14 — `starmap.js`: per-line "specimen: " prefixes removed; one "Map note" honesty line in the info strip keeps the specimen labelling (e2e honest-states gate stays green).
- UX-13 — `starmap.js`: placeholder objects ("[ an item ]/album/article/…, 'source · API-052', 'when'") replaced with honest "Nothing here yet/Nothing charted yet — arrives when X is connected" lines.
- UX-16 — `settings.html`: "Clear journal entries" → "Clear device journal (local notes only)", confirm copy updated, and the data section now states that the server-side journal is managed in the journal itself.

**Owner-decision items (leave for Rylee, unchanged by this lane):**
UX-01 chat wiring (API-010), UX-02/03 journal consolidation (API-006), UX-04 settings
binding to API-030, UX-10 projects wiring (API-079/033/034 — gate essay copy outside
the gate panel already mitigated), UX-12 interests wiring (API-051). Also UX-05/20
companion-says duplication and UX-09 (mechanical, but was outside this batch).

---

*Read companion docs before working: repo `AGENTS.md` → `AGENT_POLICY.md` → `AGENT_CONTRACTS.md` → `docs/accessibility/ACCESSIBILITY_CONTRACT.md`. The Station is the product UI; the ideals are the floor; the whimsy is the ceiling.*

