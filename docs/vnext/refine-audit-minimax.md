# Worlds design v2: refinement audit

A punch list for **one** refinement round on `worlds-design.md` and `prototype/index.html`.

Read against: `docs/vnext/worlds-design.md` (the spec), `docs/vnext/prototype/index.html` (the
prototype, CSS + JS read in full), `docs/vnext/prototype/art/` (19 pieces, 11 in use), the house
(`house/DESIGN.md`, `house/LANGUAGE.md`, `house/JOY-CURIOSITY-AND-CARE.md`, `house/tokens.css`,
`house/icon-set-README.md`), the Field Guide (`field-guide/world-tree-MAP.md`,
`field-guide/design-system-WORLD-TREE.md`), `docs/vnext/connect/connect-contract.md`, and
`docs/vnext/fixture/fixture.json`.

**Nothing here proposes changing the look, Dot, or the warmth.** Every item is either a piece the
spec already names and the prototype has not built, a behaviour that is half-built, a truthfulness
fix, or a spacing/typography correction on the existing tokens. No item adds a flourish, a sound, a
confetti, or a line of voice that is not already in `LANGUAGE.md` terms. Copy stays terse warmth;
where this document quotes a string it is the string the fix must produce, not a licence to
re-voice anything.

## How to read it

| | |
|---|---|
| **P1 — must** | Breaks a named spec requirement, a Sol gate check, the §10 acceptance path, or daily honesty. Do these. |
| **P2 — should** | A daily-use app needs it, or a state the spec names is unreachable. Do if the round has room. |
| **P3 — could** | Real but small. Cheap, safe, do last or drop. |
| **S** | Under an hour of prototype work. **M**: half a day. **L**: two to three days (none in this round). |
| **Verdict** (section 2 only) | **Works** · **Partial** · **Broken** · **Missing**, judged against the spec, in the built file. |

Line references are `prototype/index.html` so each item can be found in one jump.

## Deliberately **not** in this list

Four things a reviewer might reasonably expect are absent on purpose, and adding them would
contradict a decision in force:

- **History / activity log.** Spec §4.13 keeps "Keep history after disconnect" a disabled, named,
  unreached control with the reason "Undecided. This mockup keeps nothing", and §12 lists the
  disconnect history policy as UNKNOWN. The refinement round does not build history. What is
  built instead is per-fact `changedAt` metadata (M-05), which is not storage.
- **Single-key shortcuts.** Spec §8.2 forbids them outright ("No single-key shortcuts"). Every
  control stays on Tab / Enter / Space / arrows / Escape.
- **Any path to "approvals connected".** Sol condition 1 and spec §4.7/§10 require that no
  control, mock flag or reviewer route can make an approval look connected. Nothing in this round
  adds one.
- **A "Link ready" handoff state.** §4.7 marks it a design note, not built and not reachable.

---

# 1. Missing pieces

Screens, states, components and flows the spec names but the prototype lacks or stubs, plus the
things a daily-use app needs that neither has.

### P1

**M-01 · The counter cannot show a fact state that differs from the service word** (M)
*What*: `svcState()` only looks at facts when the service's own fixture state is `healthy`
(line 397). Notes Sync and Studio Printer start `unavailable`, so when their live fact is scripted
Stale and then Unknown, the **slip, the state chip and the receipt header never change** — only
the fact row inside the service does.
*Where*: Home slip (`slipHTML`, line 467), service detail header (`detailHTML`, 470), receipt
(`receiptHTML`, 434). Spec §4.3 state table, §9 ("a service's own state word keeps following its
fixture state; the fact carries its own state"), §10 acceptance step 2.
*Why*: Acceptance step 2 must be walked "on a service the person actually connected", and the
proof-path service Connect offers first (§4.4) is **Notes Sync**, which starts Unavailable. As
built, the reviewer connects it, publishes it, waits 90s and 60s, and the counter does not move.
*Fix*: when a fact's own state differs from the service's, put that state on the slip's peeked
fact — chip, "(simulated)", and `last known` — and add the fact's line under the slip reason. The
service word stays the service word; the fact's word is now visible where the fact is peeked. One
line in `slipHTML`, one in the detail meta row.

**M-02 · The fixture's own sentence disappears on a simulated Stale or Unknown** (S)
*What*: `lines()` returns early for any scripted service and drops `summary` (line 402).
*Where*: `lines()`, 399–409. Spec §4.3 ("**The fixture's own sentence is always shown**"; any
Worlds explanation goes *under* it), Appendix A item 8b.
*Why*: "Reachable. Index current." vanishing the moment the fact goes Stale reads as if the
service changed, and it contradicts the one rule the critique round added on purpose.
*Fix*: push the summary first, then the simulated line under it, exactly as the non-simulated
branch already does. Also fix the branch condition to use the **fact's** state, not `k`.

**M-03 · No "Replace reference" on a refused service** (S)
*What*: after "Pretend Notes Sync refused its reference", the slip says "Fix it in Notes Sync" and
offers nothing. §4.9 names the control.
*Where*: `lines()` refused branch (401), service detail. Spec §4.9 Reference refused row.
*Fix*: an inline `Replace reference` button in the detail header and on the slip's refused reason,
wired to `startConnectWith(id, 'replace', '', '#/home/'+id)` — the same call `reconnect` already
makes (781), so the Connect path and the scope pre-fill come free.

**M-04 · Settings → Replace never re-checks; the service stays Stale forever** (S)
*What*: `ref-save` (797) sets `s.ref` and announces "reference replaced. Checking now." — but
nothing checks. The `refStale` flags set by `mock-refuse` are only cleared by the Connect
`replace` path (748), not by this one.
*Where*: `ACT['ref-save']`, 797.
*Why*: A reviewer replaces the reference, is told "Checking now", and the facts stay labelled
Stale with old check times. That is a promise the code does not keep.
*Fix*: route `ref-save` through the same clearing block as the Connect replace path (clear
`refused`, clear `refStale` on facts, reset `nextChk`), then settle and announce.

**M-05 · No re-check for an ordinary connected service** (S)
*What*: "Check now" exists only where `f.sim` is set (430, 447, 494) — i.e. only on the two
scripted facts. Nothing re-reads a healthy service on demand.
*Where*: fact row, receipt Source station, Memory card. Spec §4.9 offers "Check now" for Stale;
§4.13/§11 imply a counter that can be asked.
*Fix*: show "Check now" on any fact whose state is not Live (stale, unavailable, refused), and add
`f.changedAt` alongside `f.obs` so the receipt Source station can say "checked 24s ago · changed
9m ago". `changedAt` is per-fact metadata, not history storage — it does not survive a disconnect,
which is what §4.13's disabled control is undecided about.

**M-06 · Publish can never fail, so optimistic rollback is undemonstrable** (M)
*What*: `publish()` (755) has no failure branch; §4.4 and §9 both require one ("A failed Publish
removes the optimistic slip and says why").
*Where*: `publish()`, 755–759. Spec §4.4 C6 outcomes, §9 Optimistic then settled.
*Fix*: one more About mock control, "Simulate a failed publish (mock)", consistent with §4.13's
rule that mock controls only produce failure or edge conditions. It makes Publish remove the
optimistic slip, roll the receipt back, and say "Nothing was published. Nothing changed." — and
the Back button must keep the entered reference and the chosen facts so the retry is cheap.

**M-07 · A service with zero facts cannot exist; three empty states are dead code** (M)
*What*: no connectable service has an empty fact list, so "No facts yet. Nothing guessed." (C4),
`receiptHTML`'s "No facts" branch (435) and the slip's "No facts" peek (467) can never render.
*Where*: C4 preview empty, S1 fact list, H1 slip peek. Spec §4.4 C4 empty, §4.5 ("For a service
with no facts… the fixture `emptyReason`"), §4.2 (Local Weather's empty state), §12.
*Fix*: add "Set up a provider" to Settings → Providers (Local Weather), which runs the normal
Connect flow with Local Weather's `emptyReason` and zero facts. That reaches all three empty
states and gives the Not-configured service a real job without inventing fixture data.

**M-08 · No undo after disconnect** (M)
*What*: after D1 the toast and the note offer "Reconnect", which is a fresh Connect run from the
Reference step — not an undo. A mis-click on a consequential dialog should cost one press.
*Where*: `doDisconnect()`, 725–730; `say()`, 672. Spec §4.10 offers "Reconnect"; §1 item 11 and
`JOY-CURIOSITY-AND-CARE.md` protect the person from consequence.
*Fix*: `say()` gains an optional action slot. After a successful disconnect, the toast carries
**Undo** for 6s: restore the service at its old index in `st.connected`, its selection, its
selected fact and its frame, with the same settle and the same announcement reversed. Revoke stays
two-step and un-undoable — deleting a reference should not be a single press.

### P2

**M-09 · No search over slips or facts** (M)
*What*: the only filtering anywhere is Memory's per-service `<select>` (499).
*Where*: Home slips, Memory. Daily use with 5–20 services.
*Fix*: a single search field in the Home page header, filtering slips by name, kind and peeked
value, and — on Memory — filtering fact rows within the selected service. Plain substring, no
fuzzy matching, no result ranking. Empty result shows "Nothing matched" inside the dashed well
(art gap 5). Keyboard: `/`-free, Tab-reachable, `Escape` clears.

**M-10 · Slips have no order the person controls** (S)
*What*: slips render in connection order forever.
*Where*: `viewHome`, 491.
*Fix*: a three-option sort next to the count — **Needs you first** (default, and the useful one),
then name, then freshness. Persist in `st`. At 20+ services the default matters more than the
choice.

**M-11 · No rename** (M)
*What*: the contract's `display_name` ("the owner's words") is never editable; every name is a
fixture string. §3's Trail rule also leans on names being the person's.
*Where*: service detail header, Settings → Connected services row.
*Fix*: "Rename" on the service header, an inline text field with the same checks as the reference
field (non-empty after trim, ≤40 characters, control characters refused, never rendered as
markup — contract §4.1 security test). Rename changes slip, detail header, receipt, Memory
heading and Needs-you card together; the URL keeps the connection id. This also gives M-08's
long-name test a way to exist.

**M-12 · No second connection of the same kind** (M)
*What*: ids and names are fixed by `DEFS`; two media libraries cannot both exist, so nothing
proves the UI is keyed by connection id and not by kind or name.
*Where*: Discover candidates (`CANDS`, 361), slips, Memory filter, Settings.
*Fix*: one candidate that shares a kind with an existing service — "Loft Shelf", kind "media
library", its own id `loft-shelf`, its own fixture-shaped facts. Everything else must key off the
id, unchanged.

**M-13 · Needs-you items carry no "arrived while you were elsewhere"** (S)
*What*: the badge counts, but an item you have already dealt with is indistinguishable from a new
one, and nothing ever leaves Needs you except `#simulate-change`.
*Where*: `viewNeeds`, 501; badge `navItem`, 605.
*Fix*: mark an item **New** when it enters Needs you while you are on another screen, announced
polite with the existing single live region; the mark clears when you open the item. Keep the badge
in text ("Needs you, 2") and give it no colour-only signal.

**M-14 · Nothing survives a reload** (M)
*What*: `st` is in memory only; a reload returns to `#/welcome/1` and replays first run, with the
mock clock back at 24s.
*Where*: `st`, 366; boot, 846.
*Fix*: persist to `localStorage` under one key with a version — theme, motion, cadence, live
on/off, welcomeDone, journeySeen, memFilter, the connected list with references and scopes,
`doorLocked`, and `st.now` as an absolute instant so ages continue instead of rewinding. Add
**Reset the mockup** to Settings → About so a reviewer can get back to first run. Nothing secret
goes here: references are names, and the refused-secret path already clears before this could ever
run.

**M-15 · The phone pushed screen has no Back in the top bar** (S)
*What*: §5.3 says a pushed screen has no bottom strip and "Back is in the top bar"; the prototype
puts an inline "Back to counter" text button in the content instead, and the header button still
reads "Settings".
*Where*: `updateTop()`, 614–615; `viewHome` phone branch, 490.
*Fix*: when the route has a service segment and the width is phone, the header button becomes Back
with the back chevron, targeting `#/home`, restoring focus to the invoking slip (the `st.inv`
mechanism already does this).

**M-16 · The phone welcome beats have no live or simulate controls** (S)
*What*: `placeControls()` puts the top-bar controls into `.status-slot` when one exists and into
the hidden `#controls` when one does not (621–626); the welcome renders no status slot, and
`.controls` is `display:none` under 48rem. So on a phone the first two beats have neither
`#live-toggle` nor `#simulate-change`.
*Where*: `viewWelcome`, 513–524; `placeControls`, 621.
*Why*: §5.3's status row is defined for top-level screens, and the welcome sits inside Home.
*Fix*: give the welcome beats the same `.status-slot` header on phone, or render `#live-toggle`
beside "Skip welcome".

**M-17 · Settings renders all five sections on every screen** (S)
*What*: `#/settings/{section}` only sets `aria-current` and scrolls focus to the heading; the pane
model of §5.1 (a 14rem list beside one pane) is not built. On phone `.set-nav` is `display:none`
and the anchor links are gone, so the sections are reachable only by scrolling.
*Where*: `viewSettings`, 576–598; `.set-nav`, 223.
*Fix*: render the routed section's pane plus the list on wide; on phone render the whole column
as now but add a "On this page" contents row of in-page anchors at the top. Small, and it makes
the Connect → "Manage reference in Settings" link land visibly.

**M-18 · Settings sections have no loading and no error states** (S)
*What*: §4.0 and §4.13 give every section loading, empty and error. Only empty exists. There is no
error branch anywhere in Settings, and `ref-save` has no failure path.
*Where*: `viewSettings`, 583–597.
*Fix*: a static loading panel ("Fetching settings…" with a resting Dot) on first paint of the
pane, and one mock control — "Simulate a failed save (mock)" — that makes the next reference save
fail with "Couldn't save that. Nothing was changed. Try again." and leaves the field intact.

**M-19 · "How one fact travels" can land on nothing** (S)
*What*: `journey` sets `journeySeen=false` and routes to `#/home` (804). With no service selected —
or with Memory's filter set to a different service — the note renders inside the detail pane of
whatever is selected, or nowhere.
*Where*: `ACT.journey`, 804; `journeyHTML()`, 469.
*Fix*: select the first connected service before routing, or make the note a dialog. Dialog is
better: it is a note, not a screen.

**M-20 · Offline cannot be tested on demand** (S)
*What*: only real network events set `st.offline` (842–845). A reviewer on a plane-mode toggle has
to leave the browser to see the whole X1 surface.
*Where*: About → Reviewer controls, 596.
*Fix*: one more failure/edge control, "Go offline (mock)", toggling the same state the real events
use, so the strip, the frozen ages and the paused label are all reachable. It stays in Reviewer
controls with the others.

**M-21 · The publish target (board) is never shown** (S)
*What*: the contract's `PublishSelection.board` ("must be an existing board", §4.4) has no
representation in C6 or Settings.
*Where*: C6 summary list, 568.
*Fix*: one line in the C6 summary — "Board: Home" — with no control, because Worlds has exactly
one board. If the team would rather not commit to that, record it in §12 as UNKNOWN instead of
leaving the field silently absent.

**M-22 · Connect only fails at Test** (M)
*What*: `simFail` (825) affects Test alone. Preview always succeeds after 800ms; Publish always
succeeds; Reference has no "the provider rejected this reference" outcome.
*Where*: `viewConnect` preview/publish, 558–568.
*Fix*: extend the existing mock checkbox to a three-option labelled group at Test —
**Simulate: test passes / test fails / preview and publish fail (mock)** — so the reviewer can walk
every Connect step failing and confirm the flow stays recoverable: the reference survives, the
chosen facts survive, Back works, Cancel asks nothing, and nothing is saved until Publish.

### P3

**M-23 · An already-scoped connection's scope cannot be changed** (S)
*What*: "Narrow scope" only appears when `!s.scope` (580). Replace keeps the existing scope, so
there is no way to widen or re-pick a scoped service's capabilities.
*Fix*: show "Change scope" for scoped connections too, opening Connect at Reference with the
current capabilities ticked — `startConnectWith(id, 'narrow', s.ref, …)` already does this; it
just needs the button on both rows.

**M-24 · The Add-service FAB shows where it means nothing** (S)
*What*: `no-fab` is set only for Connect, welcome and pushed screens (618), so the floating pill
sits over Needs you and Settings.
*Where*: `updateTop`, 618; `.fab-slot`, 277.
*Fix*: hide it on Needs you and Settings; keep it on Home, and on Memory only when the list is
empty, where it is the empty state's call to action.

**M-25 · About states the Field Guide fit but links to nothing** (S)
*What*: §4.13 asks for "one sentence **and link**"; the prototype has the sentence (593).
*Fix*: make it a link to `docs/vnext/field-guide/world-tree-MAP.md`, and add the two documents a
reviewer actually needs beside it — the spec and the Connect contract — as plain links that open
outside the mock rather than in the app frame.

**M-26 · The slips column has no plan for 20 services** (M)
*What*: the column is an unbounded grid with no max height, no scroll and no overflow affordance;
at 20 slips the detail pane scrolls off and the top of the counter is a screen away.
*Where*: `.home-grid`, 132; `.slips`, 133.
*Fix*: cap the desktop column to the viewport with `overflow:auto` and keep the detail pane
sticky; add a reviewer control "Add ten more candidates (mock)" so the cap, the sort, the search
and the badge can all be judged against the 20-service case rather than argued about.

---

# 2. Reactive elements

Every live behaviour the app should have, and whether it works today.

### The store and the clock

**R-01 · Live feed tick** — **Works.** `tick()` (701) advances a mock clock every second and
`refreshAges()` re-renders every `[data-ak]` span in place. Two caveats: the tick is gated on
`st.welcomeDone` (702), so nothing ages on the welcome beats — correct — and `setInterval` is
throttled in a hidden tab, so `st.now` drifts behind the wall clock until the tab is refocused.
Harmless in a mock; fix it anyway by resyncing on `visibilitychange` rather than letting the drift
accumulate.

**R-02 · Cadence 5 / 10 / 30s** — **Works** (827, 589). Ages update on the cadence boundary only,
which is what "a tick updates every age and nothing else moves" asks for.

**R-03 · Freshness ageing to Stale** — **Partial.** See M-01: ageing works, but a fact whose state
diverges from a non-healthy service's word is invisible on the counter.

**R-04 · The scripted 90s miss** — **Works** for Media Shelf; **Partial** for the Connect-armed
fact, because `connectSvc` (686–689) arms it only on a fact whose service is healthy. Same root
cause as M-01.

**R-05 · The 60s escalation to Unknown** — **Works**, value cleared to Unknown, last value kept as
"last known" with its time (692). Loses the fixture summary: M-02.

**R-06 · One change reaching every view** — **Works, weakly.** `simulate()` (709) flips the fact,
the service word, the status line, the badge, the slip, the header and Memory in one `refreshAll`,
with the settle, the nod, the "Updated now" strip and one announcement. But Home, Needs you and
Memory are never on screen together, so "one change, every view" cannot be *seen* — only visited.
**Fix (S)**: after the simulated change, the existing note names the three places that moved —
"Your counter, Needs you and Agent facts all show it now." — with the same 60ms settle. Proof
without a new screen.

**R-07 · Optimistic publish, then settle** — **Works** (755–759: slip appears, parcel travels,
stamp lands). **Rollback: Missing** (M-06).

**R-08 · Optimistic disconnect, then settle** — **Works** (725: slips, facts and frame leave in the
same frame; the message names exactly what went). **Undo: Missing** (M-08).

**R-09 · Revoke** — **Works** (731–736), including "if this empties the counter: H0" and the
"rotate it in {App}" line. No undo, by design (M-08).

**R-10 · Loading states** — **Partial.** Frame loading, preview fetching, test running and the
welcome carrying all have one. **Missing** for the Memory list, the slips list and every Settings
section (M-18).

**R-11 · Skeletons** — **Missing, and should stay missing in spirit.** §8.1 forbids shimmer. What
is right is a *static* placeholder: for Memory, three sunken rows with the word "Fetching facts…";
for Settings, one panel saying "Fetching settings…". Plain, still, no pulse.

**R-12 · Progress** — **Partial.** The step list carries numerals, checks and `aria-current="step"`
(571) and phone carries a real "Step 3 of 6 · Test" line (541). Inside a step there is no progress
word: Preview says "Fetching facts…" with no stage. **Fix (S)**: name the stage in words —
"Reading." → "Shaping facts." → done — one line, changing twice over the 800ms. Words, not a bar.

**R-13 · Toasts and the live region** — **Works**, with three things to name explicitly. The toast
is `role="status" aria-live="polite"` (327) and a separate `#alert` `role="alert"` carries the one
assertive message the test failure needs (328, 754) — that is the correct split, but §8.3 says "a
single `role="status"` live region" and the prototype has two, so the spec sentence should be
corrected to say one polite and one assertive rather than leaving the code to look wrong. The
`#alert` is cleared and rewritten after 30ms (672) so a second identical failure re-announces; some
screen readers lose a message that arrives inside the same tick — set the node only when the text
differs. And the toast has no dismiss control and no action slot (M-08).

**R-14 · Offline** — **Partial.** The strip, the paused label and frozen ages all work (842–843,
607). Two gaps: there is no on-demand way to reach the state (M-20), and the spec says offline shows
states "as Stale-with-time" (§4.14) while the prototype leaves the true words alone. **Do not
relabel them** — inventing Stale is exactly the dishonesty §10 forbids. Fix the spec line instead:
states keep their words, the strip carries the reason, and ages freeze because they would be false.

**R-15 · Reconnect** — **Works**; the strip clears after 3s (843) and the next tick resumes.

**R-16 · Background retries with backoff** — **Missing.** Nothing retries anything: a re-check that
misses simply ages into Stale. **Fix (M)**: when a re-check fails, retry the fact twice at 2s and
4s, then let it go Stale as it does now; one polite announcement on the first failure only
("Notes Sync didn't answer. Keeping the last facts."). Backoff applies to the app frame too:
"Try again" currently goes straight to a result (458).

**R-17 · Counters and badges** — **Works** (605, 611). The Needs-you badge is the count in text and
the top-bar label carries the freshest check. Two honesty fixes: the status line's "checked 24s
ago" is the **newest** check across services (`freshest()`, 374), so with Nightly Backup eight hours
stale the counter still reads "checked 24s ago" — change the word to **"newest check 24s ago"**,
and make the top bar say the same. And a new Needs-you item needs the mark from M-13.

**R-18 · State transitions and their reduced-motion forms** — **Partial, mostly good.** The CSS
zeroes every duration and both travel handles under `prefers-reduced-motion` and under the Settings
"Reduce always" switch (21–22), so the parcel, stamp, nod, settle stagger and dialog all collapse
correctly, and data never stops. Two leaks: `.btn:active{transform:translateY(.0625rem)}` (44) is
not zeroed and is a transform under reduced motion; and `publish()`/`w-connect` read
`matchMedia` directly (758, 788) rather than the `st.motion` handle on its own — they check both,
which is right, but the duplication is a trap for the next person.

**R-19 · Pause and resume** — **Partial.** `st.live` freezes the clock, the tick, the re-checks and
the scripted timers (702) — correct and important, since those timers are measured against
`st.now`. It does **not** pause anything measured against wall time: an in-flight test (754), a
preview fetch (741), a frame load (458), and a parcel mid-carry are `setTimeout`s that run on.
Pausing during a publish leaves the stamp landing on a paused feed. **Fix (S)**: give each of the
four a canceller that pause sets and resume re-arms, or hold the result until resume.

**R-20 · "Updated now" and the settle window while paused** — **Partial.** Both windows are measured
in `performance.now()` (714), so a pause does not hold them open; the toast does (`keep:!st.live`,
708), so the strip can outlive the sentence that explained it. Minor, but the mismatch is visible.

**R-21 · Animations replaying on re-render** — **Partial.** `refreshAll` rebuilds the receipt and
Memory cards, and the `settle` class plus the nod class are recomputed from `performance.now()`
(436, 493), so any render inside the 1.5s window restarts the 60ms stagger and the nod. A cadence
tick inside that window will re-tick stations that already ticked. **Fix (S)**: key the settle off
a change counter (`st.settleSeq`), and add the class only when the sequence differs from the one
the rendered node carries.

### Reactive things the spec names that have no implementation at all

**R-22 · Nothing ever becomes Needs you** — **Partial.** `st.doorLocked` (714) is the only
transition into `needs_attention`, and the only one out. So Needs you can be entered once and left
once. Not a blocker for this round — the fixture has one needs-you service — but worth one mock
edge control ("Make Studio Printer need you (mock)") so the incoming-item mark in M-13 and the
badge in R-17 have something to arrive.

**R-23 · Nothing ever changes state by itself except the two scripted facts** — **Works, by
design.** The re-check rule (698) updates `checkedAt` and never the value; §9 says exactly this.
Worth stating so nobody "fixes" it.

---

# 3. Robustness

Edge cases and failure paths. Most of these are already handled and are listed so the round does
not regress them.

### Keyboard and focus

**B-01 · "Skip to Worlds" navigates to the error screen** (S) — **Broken, and it is the first Tab.**
The skip link is `href="#main"` (308). Activating it sets `location.hash='#main'`, `hashchange`
fires, and `renderView` falls through to `viewError()` (644) because `main` is not a known route.
The person who tabs first lands on "Couldn't load this."
*Fix*: intercept the click, call `main.focus()` and do not change the hash — or handle `'main'` in
`onRoute` as a no-op. Test it first; it is one keystroke from the top of every screen.

**B-02 · Focus restoration when the focused control disappears** (S)
*Where*: `keepFocus()` (629), `renderView()` (646).
*What*: both restore by `data-fk`/id and do nothing if the element is gone — after a re-render the
focus is lost to `<body>` and the next Tab starts from the top of the document. This happens for
real on disconnect (the slip you were on is gone), on revoke, and on Memory's service filter
changing under a focused row.
*Fix*: if the key is not found, fall back to the screen's `h1` (`tabindex="-1"`), as
`focusHeading` already does.

**B-03 · Focus hidden behind the sticky top bar** (S)
*Where*: `scroll-padding-top:calc(var(--wv-top-h) + 1rem)` (25), `.rail-in{top:var(--wv-top-h)}` (70).
*What*: `--wv-top-h` is a guess (4.5rem phone, 7rem tablet). At 200% browser zoom the real bar is
far taller than the guess and a focused heading lands underneath it.
*Fix*: measure the header once with a `ResizeObserver` and write the measured height back to
`--wv-top-h`. One handler, and every sticky offset and scroll-padding becomes correct at every text
size.

**B-04 · No keyboard trap; dialogs are native** (S) — **Works.** `<dialog>.showModal()` traps and
returns focus, Escape closes, and the close handler restores by `st.dlgInv` or falls back to the
`h1` (720–721). Worth keeping the native element rather than replacing it with a div.

**B-05 · Escape on Connect works only in the confirm phase** (S)
*Where*: 837. After Publish is pressed the parcel is mid-carry and Escape does nothing, which is
right; but Escape on any step while `cxGuard` has already bounced the route is untested.
*Fix*: leave as is; add a note to the audit trail so it is a decision, not an omission.

### Input and reference handling

**B-06 · A valid-looking reference of 50+ characters is refused as a secret** (S)
*Where*: `refCheck`, 528 — `ref://` + 1–49 characters.
*What*: a 60-character reference is correct and safe, and gets the message "That looks like a
secret. Cleared, not saved." That is a false accusation and it clears a field the person did right.
*Fix*: return a distinct `'toolong'` verdict with its own one-line message ("Too long. Use a
shorter name after ref://."), and keep the field.

**B-07 · The refused secret is cleared before it can be stored or echoed** (S) — **Works, and is
load-bearing.** `cxValidate` (744) empties `c.ref` and the DOM field on a `secret` verdict, the
message never repeats the input, the aria-live region shows the fixed sentence, and nothing in the
store ever sees it. Two things to protect in the round: keep `ref-save` in Settings on the same
`refCheck` path (797 already is), and keep the Settings Replace field's clear-on-secret behaviour —
that one clears `i.value` but **not** any stored copy, because there is none; do not add one.

**B-08 · Enter in the reference field submits** (S) — **Works** (835), and the same for Settings
Replace (836). Both go through the same validation.

**B-09 · Rapid scope toggling resets the test** (S) — **Works and is correct** (823): changing the
scope invalidates a test run under the old scope, which is Sol condition 3 behaving properly.
Keep it.

**B-10 · The last chosen fact cannot be unticked** (S) — **Works** (824) and re-checks the box,
announcing "Keep at least one fact." via the polite region.

### Failure paths

**B-11 · Every Connect step failing** (M) — **Missing.** Only Test can fail (M-22).

**B-12 · An embed that refuses, then refuses again** (S) — **Partial.** `PLAN` makes Front Door
refuse and Notes Sync time out on the first try, and "Try again" always succeeds on the second
(458). A reviewer therefore never sees a persistent refusal.
*Fix*: fail the first two tries and let the third succeed, so "Try again" has a real cost and a
real payoff, and `st.frames[id].tries` is doing something honest.

**B-13 · Double-clicking a confirm button** (S)
*Where*: `dlg-disc`, `dlg-revoke`, `ref-remove`, `handoff`, `mock-stale`, `mock-refuse`.
*What*: the two halves of a double click can land on the dialog button and then the main-surface
button underneath once the dialog closes, opening it again. `publish` and `runTest` are already
guarded (`phase`, `state==='running'`); the rest are not.
*Fix*: one `st.inflight` flag set on entry to each handler and cleared on the next animation frame,
checked at the top of every confirm handler.

**B-14 · Rapid `#live-toggle`** (S) — **Works.** Toggling is idempotent on `st.live` and the label
and `aria-pressed` agree on both the top bar and `#settings-live` (609–610).

**B-15 · `#simulate-change` pressed twice** (S) — **Works.** The second press is refused by the
`st.doorLocked` guard and the toast says "Already reported locked." Make the button
`aria-disabled` after the first press rather than leaving it looking live (it also keeps a static
`aria-label` of "Simulate change: back door locked" that is no longer true — update it).

**B-16 · `#live-toggle` and `#settings-live` always agree** (S) — **Works**, and it is a Sol-adjacent
promise; keep both in step in any refactor.

### Scale and volume

**B-17 · Twenty services** (M) — **Untestable today** (M-26). Judge the slips cap, the sort, the
search and the badge against the 20 case, not the 2.

**B-18 · A very long name** (S) — **Untestable today.** `overflow-wrap:anywhere` is on `body` (26)
so nothing will clip, but nothing long exists to prove it. M-11's rename plus a 60-character name
is the test.

**B-19 · Zero facts** (M) — **Untestable today** (M-07).

### Truth of numbers and times

**B-20 · Absolute times have no zone marker** (S)
*Where*: `fmtT` pins `timeZone:'UTC'` (339) and About says "Times in UTC" (593).
*Why*: that is the honest choice for a mock, and it should stay. But "No change seen since 2:23 PM"
reads as local time unless you already know.
*Fix*: keep UTC, and put the zone in the string where an absolute time appears next to a
person's own clock — "2:23 PM UTC" in the Stale line and the receipt. One token's worth of honesty
in three places.

**B-21 · The mock clock drifts against the wall clock** (S)
*Where*: `st.now` advances only inside `tick()` (703).
*Why*: background tabs throttle `setInterval` to about once a minute, so after ten minutes away
Worlds claims "checked 24s ago" for a reading that is ten minutes old.
*Fix*: on `visibilitychange` and `focus`, add the elapsed wall time since the last tick to `st.now`
before the next render. It keeps the mock's own clock and stops it lying.

**B-22 · "Live" never appears without a real checked time** (S) — **Works.** `liveLabel` falls back
to "Not checked yet" (607) and `fs()` treats a live fact with no observation as `unknown` (371).
That is the §7.1 rule and it is implemented.

### Accessibility and rendering

**B-23 · Contrast in all four house modes** (S)
*Where*: token pairs are computed in §8.5 and pass; the prototype adds colour **outside** those
pairs and those are the risk. Three: the needs-you **badge** uses `--surface-base` as its text
colour on `--status-needs-you` (76) — a page colour used inside a chip; measure it in Light and Low
stimulation. The **Dot** and the `.hero` / `.scene` / service-icon art are images with baked
colours and cannot be measured from tokens at all; §12 already flags Dot in Light. And the
**stamp** is rotated text in `--status-done` on raised, fine in the token table but with a 2.5rem
image beside it.
*Fix*: measure the badge pair and the three art pieces on all four surfaces, in all four themes, at
desktop, tablet and phone — that is exactly the check Q9 says has not been done.

**B-24 · Screen-reader announcements** (S)
*Where*: §7.3, 501.
*What works*: routine ticks are silent (only `[data-ak]` text changes, no live region); publish,
disconnect, revoke, a state change, a failed test (assertive), pause and resume, and the
simulated-change sentence all announce once, batched.
*What to check: the receipt's settle and the nod are CSS-only and correctly silent; the `#alert`
rewrite gap (R-13); the Needs-you item mark (M-13) which must be announced once, not on every
tick; and `aria-disabled` buttons announce their reason only if `aria-describedby` points at
visible text — `#disconnect` does (613, and `#disc-reason` is rendered), and the permission `none`
control does (427). Both correct.

**B-25 · 200% browser text** (S) — **Partial.** Breakpoints are in `rem`, so layout falls back to
tablet and phone correctly, and nothing blocks zoom. The one real failure is the fixed
`--wv-top-h` (B-03). Also check the receipt stations at 200%: they are `repeat(auto-fit, minmax(12rem,1fr))`
(157), which at double size collapses to one column — correct, and it matches §5.2.

**B-26 · 320px width** (S)
*Where*: `body{min-width:20rem}` (26) is exactly 320, so 320 is the floor the design has to hold.
*What breaks*: the fixed Connect bar is `flex-wrap:nowrap` with Cancel, Back and Next (296), which
overflows at 320; and the top bar is `nowrap` with the brand, the wordmark, the MOCKUP label and a
text "Settings" button (264–266).
*Fix*: below 22rem, let the Connect bar wrap to two rows (Back/Next on the second), and shorten the
header button to the gear icon with the full name in its accessible name.

**B-27 · State persistence across reload** (M) — **Missing** (M-14).

---

# 4. Polish

Visual consistency, rhythm, hierarchy, motion timing, art placement, where Dot appears, and the art
gaps.

### Tokens and rhythm

**P-01 · Literal gaps, radii and widths outside the token ladder** (M)
*Where* (all in the prototype's stylesheet): `.nav-item{gap:.75rem}` (72), `.slip-top{gap:.75rem}`
(136), `.stamp{gap:.6rem}` (105), `.stamp img{width:2.5rem}` (106), `.btn{gap:var(--space-sm)}` is
fine but `.toast{max-width:28rem}` (246), `dialog{width:min(40rem,…)}` (238), `.hero{width:min(22.5rem,…)}`
(101), `.scene{width:min(17.5rem,…)}` (102), `.cx{grid-template-columns:14rem … 18rem}` (197),
`.set-grid{grid-template-columns:14rem …}` (223), `.fact-card{grid-template-columns:… 1.2fr … 1fr}` (185),
`.stations{minmax(12rem,1fr)}` (157), `select{min-width:12rem}` (190), `.row>div{flex:1 1 14rem}` (231),
`.msg{min-height:4.25rem}` (217), `.welcome-dot{min-height:15rem}` (120), `body{min-width:20rem}` (26),
`.frame-body{margin:var(--space-md)}` is fine, `.empty{gap:var(--space-xl)}` is fine. Plus inline
`style="margin-top:.5rem"` (507) and `style="width:100%"` (545).
*Why*: §6 says no gap, radius or text size is written as a literal outside tokens or the named
`--wv-` handles, and `house/DESIGN.md` calls a private literal "a decision that escaped review".
*Fix*: add the handful that recur to the handle block at line 18 — `--wv-measure` (40rem),
`--wv-panel-w` (14rem), `--wv-rail-aside` (18rem), `--wv-hero-w` (22.5rem), `--wv-scene-w` (17.5rem),
`--wv-min-width` (20rem), `--wv-toast-w` (28rem), `--wv-station-min` (12rem) — and route the inline
styles through classes. This is also the natural moment to answer Q8.

**P-02 · Section headings are `--type-h1` in an inline style instead of `--wv-display-section`** (S)
*Where*: Memory service headings (499), Needs-you card and section titles (506–508), Discover's
"Already connected" (545), the Settings `#sec-*` (584–596).
*Why*: §6 gives section headings `--wv-display-section` (1.85rem); `--type-h1` (1.5rem) is the
body-scale heading token and sits below it. The prototype's own `.sec-title` and `h2` do it
correctly — these are the leftovers.
*Fix*: delete the inline styles; `h2` already carries the right size and font.

**P-03 · Images start with `src=""`** (S)
*Where*: 310 (the top-bar counter icon), and every `img()` helper renders before `ART` resolves.
*Why*: an empty `src` resolves to the page URL in several browsers, which makes a stray request for
the document itself on every render.
*Fix*: `src` a 1×1 transparent data URI in the markup and let line 393 overwrite it, or add
`[data-art]{visibility:hidden}` until set.

### Hierarchy and alignment

**P-04 · The slip's peeked fact is emphasised the opposite way to the fact row** (S)
*Where*: `slipHTML` (467) — `<span>${label}</span><strong>${value}</strong>`; `factInner` (430) —
bold label, `--type-lead` value.
*Fix*: one emphasis rule for both. The value is the data, so the value is the lead: set the peek's
value at `--type-lead` and the label at `--type-small` soft, matching the row.

**P-05 · Fact rows don't stack on phone** (S)
*Where*: `.fact{display:flex;justify-content:space-between}` (149) with a right-aligned value block.
*Why*: at 320px a long label and a `--type-lead` value meet in the middle; a label like "Local notes
waiting to upload" and the value "3 notes" collide before either wraps.
*Fix*: below 48rem, `.fact` becomes a two-row grid — label and age on the first, value and chip on
the second, left-aligned.

**P-06 · "Updated now" arrives and leaves with no fade** (S)
*Where*: `.upd{color:var(--status-done)}` (84), switched by `upd()` (420) on a 3s window.
*Why*: §8.1 gives every other confirmation a 150ms cross-fade; the toast fades and this one pops,
which is the most-visible motion seam in the app.
*Fix*: give `.upd` the same opacity transition at `--wv-dur-state` on `--wv-ease`. One rule.

**P-07 · The slip peek and the fact value use different alignment from the receipt** (S)
*Where*: `.slip-peek{justify-content:space-between}` (140), `.slip-foot` likewise.
*Fix*: keep label left and value right, but give both a `min-width:0` and let the value wrap rather
than push the label to a single-word column at 320px.

### Where Dot appears, and where it should stay quiet

Current placements, checked against §1 items 5–13 and §4.0's Carries column:

| Where | Dot | Verdict |
|---|---|---|
| W1 welcome card | asleep, `lg`, with "Dot's asleep." | Correct — the signature |
| W2 beat | `hero-welcome` then parcel then nod | Correct |
| W3 beat | `dot-welcome`, no hero art | Correct but plainer than W2 (art gap 2) |
| Freshness line, every screen | rest, or nod during a change | Correct — the resting rule |
| H0 empty counter | **none** (the `empty-counter` scene instead) | **Wrong** — §4.2 says Dot asleep in a dashed well |
| H1 slips and detail | none | Correct |
| Stale service header | `dot('curious')` next to the chip (476) | A pose with no sentence — see P-08 |
| Receipt, facts, Agent/Human lines | none | Correct — the counter, not the snail |
| Needs-you item cards | none | **Correct** — this is the rule holding |
| Needs-you empty | asleep, `lg` | Correct |
| Memory empty | asleep, `lg` | Correct |
| Settings | none beyond the resting line | Correct |
| Dialogs (disconnect, revoke, handoff, owner) | none | **Correct** — quiet on consequential surfaces |
| App frame loading | rest, small | Correct |
| Test running, preview fetching | rest | Correct — static, no motion |
| Load-error screen | rest, **`lg`** (599) | Too loud — see P-09 |
| After disconnect | `dot-goodbye` in the note (423) | Correct and lovely; keep |
| Stamp | Welcome and Publish only | Correct — the one flourish |

**P-08 · The `curious` pose on the stale header is a flourish without a sentence** (S)
*Where*: `detailHTML` line 476 renders `dot('curious')` beside the Stale chip.
*Why*: §1 item 6 fixes Dot's behaviour to four named poses with rules — asleep, nod, parcel, rest.
Curious is drawn and available but has no rule, and here it sits where §1 item 13 says motion
should not appear: nothing has changed yet, the fact simply aged.
*Fix*: drop it. The Stale chip, the word and the "No change seen since…" line carry it, and the
resting Dot stays in the freshness line where the rule puts it. `dot-curious.webp` can stay in the
art folder for a moment that earns it.

**P-09 · The load-error screen leads with a 160px Dot** (S)
*Where*: `viewError` (599) uses `dot('rest','lg')` where `.dot.lg` is 10rem (93).
*Why*: §4.14 says "Dot rests; no blame". A screen whose whole message is "we couldn't load this"
should be the quietest screen in the app, and a 10rem snail is not quiet.
*Fix*: use the resting size. The dashed well, the sentence and the two buttons carry it.

**P-10 · H0 has no Dot** (S)
*Where*: the empty counter (489) uses `empty-counter.webp` and no Dot at all.
*Why*: §4.2 says "Dot **asleep** in a dashed-outline well" and §4.0 lists item 6 (asleep) as carried
by H0. The scene is good; Dot is simply absent, and "asleep" is a state the person should be able to
see.
*Fix*: put `dot-asleep.webp` in the well beside the scene at rest size, with the existing sentence
as its accessible context. **No new art** — `dot-asleep` already exists and is already in the
bundle.

### Art placement

**P-11 · `icon-local-weather.webp` is generated and never placed** (S)
*Where*: `sico()` is called only from slips, the service header and Discover (392, 468, 476, 545);
Local Weather has no slip by design (§4.2), so its icon is dead weight in the bundle.
*Fix*: place it in the Settings → Providers row beside the name. §6's rule is a painted icon always
sits beside its word, and this one already has its word waiting.

**P-12 · Service icon sizing is correct; two placement notes** (S)
*Where*: `.sico{height:2rem}`, `.sico.sm{1.75rem}`, `.svc-id .sico{2.5rem}` (94–99); nav glyphs are
plain inline SVG (382).
*Verdict*: **Correct as built.** Every painted icon is above the house's 20px floor and well above
its 16px non-reading threshold. The house's sticker set (`ui-planet`, `ui-star`, `ui-bell`,
`ui-people`) is the production swap for the nav; the prototype's line glyphs are the documented
stand-in (§6) and should stay stand-ins in the mock. Do not import sticker art into the prototype —
it would put painted pixels beside line glyphs in the same bar.

**P-13 · The `.stamp` is rotated −4° with uppercase serif at `--type-lead` and a 2.5rem image**
(P3, S)
*Why*: at the smallest phone size the rotated box's corner can clip against its own line-height, and
the tilt makes the baseline sit off the panel grid.
*Fix*: give `.stamp` a small `padding-block` and check the tilt at 320px; nothing else.

**P-14 · `--wv-travel:-10rem` is a guess at the lane's width** (P3, S)
*Where*: 18 and 110.
*Why*: the parcel travels from off-lane-left by a fixed distance; at 320px the lane is narrower than
10rem and Dot starts outside its own clipping box.
*Fix*: make the lane `position:relative` and the Dot's start `translateX(-100%)` of its own width,
so travel is proportional at every width.

### Art gaps — new pieces needed

Six at most, all in the existing generated style (line art, apricot shell, mint body, transparent
keyed WebP, per `art/PROVENANCE.md`). Nothing here is a new visual language.

| # | Piece | One line |
|---|---|---|
| 1 | `dot-settled.webp` | Dot standing with the ribboned parcel set down beside it, for the "X is here" moment after a publish — today that moment reuses `dot-nod`, which already means "updated now", so one image is carrying two meanings. |
| 2 | `hero-front-door.webp` | A welcome hero for the W3 beat, composed and coloured like `hero-welcome.webp`, so the second connection is not the plainer of the two beats. |
| 3 | `scene-quiet-needs-you.webp` | The Needs-you empty well: Dot asleep beside one small hand-lettered card, in the `empty-counter.webp` composition, so the quietest screen has a scene rather than a bare 10rem snail. |
| 4 | `icon-generic-service.webp` | A neutral line-art service mark — a small counter with a bell — for any kind the icon set doesn't cover, so a slip never silently loses its icon (`sico()` returns an empty string today). |
| 5 | `scene-no-match.webp` | A search or filter with no results: Dot peering into an empty paper tray, for "Nothing matched". Only needed if M-09 ships. |
| 6 | `scene-frame-refused.webp` | A small line-art doorframe with Dot just outside it, for the app frame's refused and timeout bodies, so S2 stays quiet but not bare. Only if those bodies read as empty at phone size. |

**Reuse, not new art:** the H0 asleep Dot is `dot-asleep.webp` already in the bundle (P-10); the
Providers row icon is `icon-local-weather.webp` already drawn (P-11). Art gaps 5 and 6 drop out
cleanly if search and the frame polish are cut.

### Motion timing

**P-15 · Durations are named handles and used consistently** (S)
*Where*: 18–22. `--wv-dur-state` 150ms (120 phone), `--wv-dur-stagger` 60ms, `--wv-dur-sheet` 200ms,
`--wv-dur-nod` 200ms, `--wv-dur-carry` 400ms (300 phone), one `--wv-ease`. Every figure matches §6
and §8.1, including the phone variants.
*Fix*: only the two leaks — zero `.btn:active`'s transform under reduced motion (R-18), and route the
two `matchMedia` reads through the `st.motion` handle so there is one source (R-18). Otherwise this
is the part of the prototype that is exactly right and should be protected in the round.

**P-16 · The tab bar's current-page indicator is a 1px mint top border** (S)
*Where*: 273.
*Why*: a hairline is the weakest possible "you are here" on the bar that most needs one, and §6's
rule is that interactive emphasis uses `--action-primary` with more than a hairline.
*Fix*: raise it to `--wv-hairline` ×2, or give the current tab the sunken surface and keep a full
`aria-current="page"` word — the word is already there.

---

## Round exit check

The round is done when, in one pass over the built file:

1. **P1 is closed** — M-01 to M-08 and B-01 in particular, because M-01 is the §10 acceptance path
   and B-01 is the first Tab on every screen.
2. **The §10 proof path is walked end to end** on a service the reviewer connected: welcome (skip
   *and* two connections) → discover → reference with a refused secret and a chosen scope → a failed
   test then a pass → preview → choose → publish → that service's fact going Stale at 90s and
   Unknown at 60s → out to the owning app → revoke → disconnect → the counter empty and Worlds still
   working.
3. **Keyboard only**, focus visible, focus returning, Escape closing — starting with the skip link.
4. **390px**, one bottom strip, 44px targets, no sideways scroll.
5. **All four themes and reduced motion on**, with the art measured rather than assumed.
6. **Sol's gate checks re-run** — no approvals-connected path, no executable proposal, no test
   without a scope, "Unscoped" visible after the About control.
