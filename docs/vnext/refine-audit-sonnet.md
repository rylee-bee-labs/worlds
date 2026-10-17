# Worlds design v2: refinement audit

Status: MOCKUP audit. Input to ONE refinement round. Changes nothing but this file.

Rylee, 2026-10-13: "I love this. Let's send back for one round of refinement and to get every additional piece down and all the reactive elements we might need. Please. I'd like this to be a little robust and polished along with our whimsical snail."

## How this was done

- Read: `worlds-design.md` (all of it), the whole of `prototype/index.html` (CSS, markup and the JS, with the embedded art skipped), `prototype/art/` (files, pixel sizes, `PROVENANCE.md`), `connect/connect-contract.md` (the verbs and §4 field ledger), `house/` (LANGUAGE, DESIGN, JOY, tokens), `field-guide/` (glossary), `fixture/fixture.json`.
- **Not done: the prototype was not run in a browser.** Every "works / broken" call below comes from reading the code. Items marked **(read)** are code facts; items marked **(spec)** are the spec saying something the prototype does not do; items marked **(check)** are likely but need a browser or a screen reader to confirm. Q9 in the spec (nothing measured on the built prototype) still stands.
- Nothing here contradicts a decision in force. Protected: the look, Dot, the warmth and delight, and terse-warmth copy. Every new string proposed below is written in that voice and is a proposal, not final. Where an item touches a spec rule (not a decision), it says so and asks for the spec to move with it.

## Scheme

- **Priority.** **P0**: breaks a spec rule, a trust rule (§10), or accessibility; fix this round. **P1**: a daily-use app needs it; do this round. **P2**: polish; do if the round has room.
- **Size.** **S** under half a day. **M** about a day. **L** several days or touches the store.
- Each item: **What** · **Where** · **Why** · **Fix** · **Size**. IDs are stable: `M-` missing, `R-` reactive, `B-` robustness, `P-` polish.

## Round shape (recommended order)

1. **Store first (L).** R-1 (persisted store with a real clock), R-2 (event log), M-1 (service instances with ids, names). Almost every other item reads from these.
2. **Then the P0 correctness fixes** (R-3 to R-9, B-1 to B-9). Mostly S.
3. **Then the missing screens** (M-2 to M-12) on top of the store.
4. **Then polish and art** (§4). Art can be generated in parallel from the start; list at the end of §4.

Counts: 28 missing, 32 reactive, 36 robustness, 28 polish, 6 new art pieces.

---

## 1. Missing pieces

Screens, states, components and flows the spec names but the prototype lacks or stubs, plus what a daily-use app needs that neither has.

### 1A. Spec names it; prototype lacks or stubs it

**M-1 · Services are fixed fixtures, not instances. P0 · L.**
- **What:** Seven hard-coded ids (`DEFS`, `ORDER`, `CANDS`). A person cannot connect two services of the same kind (two Garden Cameras, two printers), cannot name one, and nothing can be added that is not in the fixture.
- **Where:** `DEFS`/`svcs` in the JS; `viewConnect` Discover (`CANDS.filter(!connected)`); spec §4.4 "Proof-path services", §3 "A service is not a destination".
- **Why:** "Multiple services of the same kind" is a day-one need; a second camera today is impossible, and a Discover list that empties after six connects reads as a dead end.
- **Fix:** Split *kind template* (fixture entry) from *instance* (`{instanceId, templateId, displayName, ref, scope, ...}`). Instance id = `templateId` for the first, `templateId-2`, `-3` after. Discover lists templates always, with "Already connected ×1" beside any that are; picking one makes a new instance. Routes use `instanceId`. Keep ids stable for the checker (`#disconnect-media-shelf` stays). Names default to the template name, then "Garden Camera 2" until renamed (M-3).

**M-2 · Replace reference from a refused service (spec §4.9). P0 · S.**
- **What:** The spec's Reference-refused state offers "Replace reference" (opens Connect at Reference, field empty). The prototype has `mode:'replace'` code in `cxNext` and `cxBar` but **nothing ever starts it**, and no button exists on the service surface. (read)
- **Where:** `lines()` refused branch, `detailHTML`, `ACT`, spec §4.9, §7.2 "Reference refused".
- **Fix:** Add a "Replace reference" button to the Source station and the slip detail when `s.refused`; wire it to `startConnectWith(id,'replace','', '#/home/'+id)` with an empty field. Also add "Open Memory app" (the owner link) beside it.

**M-3 · Rename a service. P1 · M.**
- **What:** No rename anywhere. The contract's `display_name` is owner-chosen and "length-bounded; never rendered as markup".
- **Where:** Settings > Connected services row; service header.
- **Fix:** "Rename" text button on the Settings row and a small pencil-free "Rename" in the service header's overflow. Inline field, label "Name", max 40 characters with a live "12/40", Enter saves, Escape cancels, focus returns to the Rename button. Empty reverts to the template name with the line "Empty. Kept {name}." Updates everywhere in one pass (R-1). Announce "Renamed to {name}."

**M-4 · Re-test a connected service. P1 · M.**
- **What:** The safe test exists only in the Connect flow. After publishing, nothing re-runs a read to check the reference still works; Replace in Settings (`ref-save`) swaps the string with no test at all. (read)
- **Where:** Settings > Credential references row; service header; contract verb `test` ("independently re-runnable").
- **Fix:** "Test again" on every reference row and on the Source station. Opens a small inline panel (not the full flow) with the same C3 states: idle, running, passed (N facts read, nothing changed), failed (cause, try n of 3, limit). Results feed the store: a pass sets `checkedAt` on the facts it read; a failure after three tries marks the service Unavailable with the classed cause "Didn't go through." Reuse the C3 component.

**M-5 · Replace reference runs the same checks and the test. P0 · S.**
- **What:** `ref-save` accepts any `ref://` shape, never clears `s.refused`, never resets scope or test, and says "Saving…" for nothing. A Notes Sync refused via the About control stays refused forever after a Settings replace. (read)
- **Fix:** On save: validate → pending (static "Saving…", field read-only) → clear `refused` → run the M-4 test → on pass, facts return to Live with "Checking now" then real `checkedAt`; on fail, keep the old reference and say why. One code path for Replace in Settings and Replace in Connect.

**M-6 · Failed Publish (spec §4.4 C6, §9). P0 · S.**
- **What:** Spec: "A failed Publish removes the optimistic slip and says why." The prototype has no way to fail a publish and no rollback code. (read)
- **Fix:** Add an About reviewer control "Make the next Publish fail" (failure/edge only, allowed by §4.13). On publish with it set: slip appears in the same frame, 900ms later removes itself, Connect returns to the Publish step with "Didn't publish. Nothing was added. Try again." (assertive once), focus on Publish. Reset the control after use.

**M-7 · Settings sections have no loading, empty or error states (spec §4.13, T1-T5). P1 · M.**
- **What:** All five sections render at once; none has loading or save-failed; "Couldn't save that. Nothing changed. Try again." is in the copy table and never appears. (read)
- **Fix:** Section component with three states. Loading: still Dot + "Fetching settings…" (static, per §4.14). Error: the §7.2 sentence plus "Try again". Add About reviewer control "Make the next save fail" so the path is reachable, with optimistic-then-rollback (R-12).

**M-8 · Settings is one long scroll, not sections. P1 · M.**
- **What:** Spec §4.13: section list beside a pane (desktop/tablet). Prototype renders all five sections stacked, nav links just scroll/focus, and `aria-current` never follows. Every route change re-renders the whole page, which wipes the open Replace field (B-12). (read)
- **Fix:** Render only the section in `#/settings/{section}`; section nav is real links with `aria-current="page"`. Phone: nav becomes a list of the five sections first, each a pushed screen with Back (spec §5.3 says one column of headings; pushed screens fit the phone pattern better, so propose this as a spec amendment).

**M-9 · `disabled` service state is missing. P2 · S.**
- **What:** The fixture vocabulary and `LANGUAGE.md` list `disabled`; the prototype's `SW` map has no `disabled`, and the spec's six state words do not either. (read)
- **Fix:** Decide in this round: either add "Disabled" (glyph: dash in square; word "Disabled"; line "Turned off in {App}.") or write one sentence in §4.9 saying Worlds never shows it because no fixture service uses it. Recommend the latter plus a defensive render in `chip()` so an unknown state prints its word and never throws.

**M-10 · Welcome beats have no "step" cue and two Back/Skip arrangements. P2 · S.**
- **What:** W2/W3 duplicate Back in the markup (two near-identical conditionals), no "1 of 3" line, W1 has no Back (fine). (read)
- **Fix:** One conditional; add a quiet "1 of 3" in `--type-small`; keep Skip on every beat.

**M-11 · Kept-out facts cannot be brought back. P1 · M.**
- **What:** Choose is the only moment to pick facts. Afterwards the note "1 fact kept out. Your choice." is a dead end; to change it a person must disconnect and reconnect.
- **Where:** Service surface "kept out" line; contract `PublishSelection.hidden`.
- **Fix:** "Change what's shown" text button on that line → reopens C5 with the current selection ticked, "Save" applies in one pass (store), "Cancel" drops. Names the kept-out facts instead of a count: "Kept out: Guest code last used by."

**M-12 · The "first receipt note" is a one-shot, then Settings-only. P2 · S.**
- **What:** After "Got it" the journey is only in About, and the About control (`journey`) sets `journeySeen=false` then routes Home, where the note appears above the receipt of whatever is selected, even a service that is not Media Shelf. (read)
- **Fix:** Pin its example to Media Shelf's fact regardless of selection; show only when the selected service is Media Shelf or as a small modal-free panel on About itself.

### 1B. A daily-use app needs it; neither has it

**M-13 · Search and filter of slips. P1 · M.**
- **What:** Home lists every service in connect order with no search, no filter. Memory has a service select only.
- **Where:** Home slips list; Memory.
- **Why:** At 8+ services the counter is a scroll; at 20+ it is unusable (B-17).
- **Fix:** One search field above slips (label "Find a service", search by name, kind, owner app, fact label), plus a state filter as a row of toggle chips: All · Needs you · Stale · Unavailable · Unknown (each with its count, text not colour). Show only when more than 6 services are connected, otherwise it is noise (keeps the quiet look for the common case). Results announce once: "3 of 12." Empty result: M-24. Memory gets the same field plus state chips; its select stays. Persist the filter in local state (B-22).

**M-14 · Sorting. P1 · S.**
- **What:** Order is connect order; Needs you is not prioritised; the attention count is not mirrored in order.
- **Fix:** Default sort "Needs you first" (then Unavailable, Stale, Unknown, Healthy; ties by name). A small "Sort" select (Needs you first · Name · Recently checked · Newest). Keep DOM order = reading order = visual order. Dot does not react to sorting.

**M-15 · Needs-you inbox is a screen, not a feed. P1 · M.**
- **What:** Needs you shows only *current* `needs_attention` services. Nothing records that something needed you and resolved; a person who looks away misses it. No per-item dismissal/acknowledge, no "seen" state, no badge on the tab title.
- **Where:** N1; nav badge; document title.
- **Fix:** Add two quiet things only: (1) a "Recently cleared" list below the items (last 5: "Front Door. Cleared 2:31 PM UTC. Home reported it."), sourced from the event log (M-16), read-only; (2) `document.title` becomes "(1) Needs you · Worlds" when count > 0 so a background tab says it. No push notifications, no sounds: Worlds shows, never pesters. State in the spec that browser notifications are deliberately out.

**M-16 · History / activity log. P1 · L.**
- **What:** No record of what changed: state changes, publishes, disconnects, replaced references, failed tests. `note` holds one message and vanishes on navigation (`st.note.view !== v`). The disabled "Keep history after disconnect" row confirms history is undecided; an *in-session* log is not that decision.
- **Fix:** A session event log (in the store, R-2): `{at, kind, service, text}`. New Settings section **Activity** (or a "Recent" disclosure at the foot of Home): newest first, one line each ("2:31 PM UTC · Front Door · Back door locked. Home reported it."), times from the mock clock, "simulated" where simulated. Capped at 200; empty state: M-24. It does *not* survive disconnect of the service beyond what's already in the session and says so: "This session only. Nothing is kept after you disconnect." keeps Q-history honest. The toast and the last-change note both become views over this log, so the undo (M-17) has something to point at.

**M-17 · Undo after disconnect. P1 · M.**
- **What:** After disconnect the only way back is "Reconnect", which drops the person into Reference and then makes them re-run Test, Preview, Choose and Publish. The note vanishes on navigation. The last-known values are gone.
- **Where:** `doDisconnect`, `note`, D1.
- **Fix:** Keep a **snapshot** of the removed service in the store for 30 minutes of mock time (or until another disconnect of the same service). "Reconnect" restores it exactly (same facts, selection, kept-out) in one step with the parcel; "Reconnect and re-check" opens Connect. The undo stays available from Settings > Connected services as a "Recently disconnected" list (this is the "Held, unused" idea made reachable), not only from a note that disappears. Revoke has no undo (the reference is gone); its confirm says so already.
- **Why it is not the history decision:** it is in-memory, time-boxed, and says "This session only."

**M-18 · Help and About as a place. P1 · M.**
- **What:** About is a paragraph block at the foot of Settings with the MOCKUP words, UNKNOWN list in one run-on, and mock controls mixed with replay buttons.
- **Fix:** Split **About** (MOCKUP, synthetic, times in UTC, Field Guide link, the UNKNOWNs as a short list, version) from **Help** (new section: "What are the words?" with the six state words and their glyphs each in one line; "What's a reference?"; "Who can act?"; "Replay the welcome"; "How one fact travels"; "Keyboard", a short list of how to do every job without a mouse) and **Reviewer controls** (own section, heading "For reviewers", collapsed by default, never inline with Help). Dot waves in Help's header (`dot-welcome`, existing). Terse: each entry ≤ 2 sentences.

**M-19 · First-run replay is destructive to the counter. P1 · S.**
- **What:** `replay()` sets `welcomeDone=false` and walks W1-W3 on top of live services. W2's "Connect Media Shelf" calls `connectSvc` which `resetSvc`s the service: its facts, scripted stale state, kept-out choices and checked times are wiped. (read)
- **Fix:** Replay is a *tour in a copy*: run the beats against a throwaway store (or just skip the connect and show the parcel/stamp animation with a "Replay. Nothing changes." line). Never mutate real instances. Label the beat chrome "Replay".

**M-20 · Reset the demo. P1 · S.**
- **What:** `#simulate-change` is one-way ("Already reported locked."), the stale scripts fire once per session, and nothing can restore a clean first-run state without a page reload (which, today, also wipes the theme, B-22).
- **Fix:** Reviewer control "Start over (clears this browser's Worlds mock)" with confirm. Also make `#simulate-change` reversible for the reviewer: "Home reports it unlocked again" in the reviewer section only (a failure/edge control, allowed by §4.13).

**M-21 · Settings: edit a credential reference's scope without leaving. P2 · M.**
- **What:** Only unscoped refs get "Narrow scope", which jumps into the Connect flow. A scoped reference's scope cannot be changed at all.
- **Fix:** "Change scope" on every row opens the C2 capability list inline in the row (same checkbox component, ≥1 required, sentence "Used only to read: …"), Save runs the M-4 test.

**M-22 · Notifications / "what changed while away". P2 · M.**
- **What:** No catch-up when the tab regains focus after a pause (R-16).
- **Fix:** On `visibilitychange` back to visible after > 60s: one line in the status area "Away 4m. 1 thing changed." linking to Activity. Never a modal.

**M-23 · Provider rows are read-only and fixed. P2 · S.**
- **What:** Providers shows Local Weather only, hard-coded. With M-1 any `not_configured` template belongs here.
- **Fix:** List every template that is not instantiated and has no reading; each row: name, Not configured, owner link. No "Set up" button (setting up is Connect's job; link "Connect" → Discover with it preselected).

**M-24 · Empty states for every list. P0 · M.**
- **What:** Audit of every list against spec "dashed empty well" rule and Dot-asleep use:

| List | Today | Needed |
|---|---|---|
| Counter (H0) | Done: Dot asleep, "Quiet here." | none |
| Memory empty | Done | none |
| Memory, service with zero facts | **Heading with nothing under it** (read) | "No facts. {emptyReason}" under the heading |
| Memory filtered to nothing (new search, M-13) | n/a | Dashed well, Dot peeking (NEW ART: dot-peek), "No matches." + "Clear filter" |
| Needs you empty | Done (Dot asleep) | keep; add "Recently cleared" if any (M-15) |
| Owner retries (none) | Section hidden | fine, hidden is right |
| Proposals | Always the sample | fine; spec says one sample |
| Discover with no candidates | plain "Nothing else to connect." paragraph styled as `.empty` | dashed well, one line, "Add another of a kind you have." with M-1 |
| Settings > Connected services | text in `.empty` | ok |
| Settings > References | plain `muted` paragraph, not the well | same dashed well as the others |
| Settings > Held, unused / Recently disconnected (M-17) | n/a | "Nothing held." |
| Activity (M-16) | n/a | "Quiet so far." Dot asleep optional; quiet tray art (NEW: empty-ledger) |
| Facts list on a service with zero facts | no list, receipt says "No facts" | fine; add the owner link (it is missing) |
| Agent view tab, zero facts | muted `emptyReason` | same dashed well |
- **Size:** M in total (several S).

**M-25 · Owner link opens a dialog, not a "note" in place. P2 · S.**
- **What:** Spec §4.6: "opens a small note". Prototype opens the modal dialog for every `app://` link, including from the handoff dialog (replaces its content, and Close then returns to the *original* invoker, not the handoff). (read)
- **Fix:** Use a non-modal popover note anchored to the link (focusable, Escape closes, focus returns to the link). Keeps the handoff dialog open underneath.

**M-26 · Frame: the cancelled state and the tab-off state. P2 · S.**
- **What:** `cancelled` exists in code but not in the spec table; frames load while their tab is hidden (phone Facts tab), burning the first-try failure on a pane nobody can see. (read)
- **Fix:** Add `cancelled` to spec §4.6 and the §7.2 copy ("Cancelled." exists). Start the frame load only when the App pane is visible (desktop: when the pane is in view or on first open; phone: on tab select).

**M-27 · Connect: Back leaves the flow with no summary on cancel after work. P2 · S.**
- **What:** Escape in the reference field drops the whole flow, including a reference the person just typed (B-9).
- **Fix:** Spec decision, flagged here: if the step has typed or ticked anything, Escape first returns focus to the page heading and shows "Nothing saved yet. Press Escape again to leave."; a second Escape leaves. Cancel button leaves at once.

**M-28 · Time zone control. P2 · S.** See B-21 for the bug; the missing piece is a setting: Settings > Live feed: "Times" · UTC (mock default) · This device. Everything relative is unaffected.

---

## 2. Reactive elements

Every live behaviour, whether it works, evidence, and the fix. "Works" means correct in the code as read.

### Status map

| Behaviour | Spec | Prototype | Verdict |
|---|---|---|---|
| Live feed tick | §9 | `setInterval(tick,1000)`; ages repaint every `cadence` s | Works, clock drifts (R-3) |
| Freshness ageing | §9 | `refreshAges()` from `checkedAt` | Works; no "d" unit, no "now" (R-4) |
| Per-fact re-check | §9 | `stepFacts` 30s | Works; header label can outlive it (R-7) |
| Scripted stale → unknown | §9 | 90s, 60s | Works; settle animation hits wrong service (R-5) |
| Unknown on silence | §4.9 | only the scripted case | Partial: no silence rule for real facts (R-6) |
| One change → every view | §9 | `refreshAll()` re-renders `#main` + nav | Works, heavy-handed (R-1, B-12) |
| Optimistic Publish/Disconnect/Revoke | §9 | in-frame add/remove | Works; **no rollback path** (R-12) |
| Loading | §4.14 | still Dot + sentence in frame, test, preview | Partial: no Settings/route loading (R-14) |
| Progress | §4.4 | none | Missing (R-15) |
| Toast + live region | §7.3 | one toast + one alert + several `aria-live` | Partial: overwrites, duplicates, 3.6s (R-9, R-10) |
| Offline / reconnect | §4.14 | strip + pause | Partial: states not shown as Stale, no recheck (R-16, R-17) |
| Retries with backoff | none | none | Missing (R-18) |
| Counters/badges | §3 | attention count, badge | Works; badge cap and title missing (R-20) |
| State transitions | §8.1 | CSS keyframes, tokenised | Works except the cross-fade (R-21) |
| Reduced motion | §8.1 | tokens zero out | Works; two gaps (R-22) |
| Pause/resume | §9 | `toggleLive` | Works; interacts badly with offline (R-23) |

### Items

**R-1 · One store, persisted, with an event log. P0 · L.**
- **What:** State lives in one module-level object `st` plus `svcs`; nothing is stored. Every change calls `refreshAll()` which throws away `#main`'s DOM and rebuilds it (R-8 and B-12 are consequences). (read)
- **Fix:** A small store with `get/set/subscribe`, selectors for each view (counts, slips, facts), and an append-only event log (M-16). Views subscribe to the slice they draw. Re-render by slice so a tick repaints ages only and a state change repaints the three places it appears. Persist the user-owned part (theme, motion, cadence, welcomeDone, connected instances and their references, filters) to `localStorage` under one versioned key, never anything that looks like a secret, with a "Start over" (M-20). Keep the mock clock offset out of storage (B-22).

**R-2 · Event log feeds toast, note and activity. P1 · M.**
- **What:** `say()` writes one string to one toast; `st.note` holds one note. Two messages in the same second lose the first (read).
- **Fix:** Everything that `say()`s first appends to the log; the toast/live region reads from a queue (R-10).

**R-3 · Mock clock drifts and stops in background tabs. P0 · S.**
- **What:** `tick` does `st.now += 1000` per interval fire. Browsers throttle hidden-tab timers (to 1/s, then 1/min), so the "real time" mock clock falls behind; also `tick` returns early until `welcomeDone`, so the clock is frozen while someone browses Memory or Settings during the welcome. (read)
- **Fix:** `st.now = T0 + (performance.now() - t0) - pausedTotal`. Tick only schedules repaints. On `visibilitychange` visible, catch up: apply every scripted event whose time passed, in order, then render once. The welcome should not freeze the clock (it should run from page load; stale timers still arm at connect).

**R-4 · Relative time is missing a unit and the "now" case. P0 · S.**
- **What:** `shortAge` tops out at hours: Nightly Backup's last success (Oct 9) reads "checked 100h ago"; a fact checked this second reads "checked 0s ago". (read)
- **Fix:** `<5s` → "just now" ("checked just now"); `<60s` s; `<60m` m; `<24h` h; else d ("checked 4d ago"). Between 1 and 2 units: "1h 12m" only past 1h under 6h? Keep it terse: single unit, no second unit. Add the absolute time as `title` and as visually hidden text on stale values ("Oct 9, 6:00 AM UTC").

**R-5 · Scripted stale does not settle the receipt, and does not nod. P0 · S.**
- **What:** `tick()` sets `settleUntil` on a stale/unknown event but never `settleSvc`, so the settle class goes to whichever service was last set (or none). It also sets neither `nodUntil` nor `updUntil`, so the §1 gesture 10 ("receipt settling") and "Dot nods beside Updated now when a state word changes" do not happen on the one change the proof path is built on. (read)
- **Fix:** `stepFacts` returns `{service, fact, to}`; the tick handler sets `settleSvc`, `settleUntil`, `nodUntil`, `updUntil` exactly as `simulate()` does. Then schedule the re-render at expiry (as `simulate.t` does) so the class clears.

**R-6 · Unknown-on-silence has no general rule. P1 · M.**
- **What:** Unknown only comes from the scripted escalation. A live fact whose re-check never lands (offline, paused, or the service flips Unavailable) just keeps saying Live and an ever-larger age. (read)
- **Fix:** Spec Q6 leaves the production rule unknown, so make the prototype's rule explicit and visible: *a Live fact with no successful check for 3× its re-check interval (90s) shows Stale; for 5× (150s) shows Unknown.* Apply to every live fact, not only the two scripted ones; the scripted events become the *demonstration* of this rule at a shorter fuse, not a special case. Keep "(simulated)" wording. Document in §9 and §12 (Q6).

**R-7 · "Live" in the header can contradict the data. P1 · S.**
- **What:** `liveLabel()` says "Live · checked 24s ago" using the freshest `checkedAt`. A service's `checkedAt` only advances while it is Healthy; with only Front Door (Needs you) connected, nothing re-checks and the bar reads "Live · checked 6m ago". Spec: Live means a real, recent check. (read)
- **Fix:** If the freshest check is older than 2× the re-check interval, the toggle reads "Live · nothing re-checking" (terse: "Live · none current") and the status line says the same. Never "Live" beside a number over 60s without that qualifier.

**R-8 · Re-render replaces focused/edited DOM. P0 · M.** See B-12 (same root cause).

**R-9 · The toast is a single overwritten slot. P0 · S.**
- **What:** One `#toast` + `#alert`; the second message wipes the first; "Test failed." is spoken twice (toast `role=status` and `#alert`). There are also `aria-live` regions inside re-rendered markup (`#ref-msg`, the test result, `#rep-msg`), which breaks the spec's "one polite live region" and is unreliable (a replaced live region is not announced). (read)
- **Fix:** One `role=status` region, created once and never re-rendered; the toast visual is a *view* of its last message. Queue: messages within 500ms batch with " · "; the polite queue never speaks more than one message per 2s. The assertive channel is used only for failed test and failed publish and does not also write the polite one. Move the field messages (`#ref-msg`) to plain text tied by `aria-describedby` and push their announcement through the same region.

**R-10 · Toast lifetime and placement. P1 · S.**
- **What:** Fixed 3.6s regardless of length (the revoke sentence is 80+ chars), no hover/focus pause, no dismiss, no queue; on phone its `bottom` equals the FAB's `bottom`, so they overlap. (read)
- **Fix:** Duration `max(4s, 60ms × characters)`; pause while hovered or containing focus; a small "Dismiss" text button when it carries an action ("Reconnect"); phone: toast sits above the FAB (`bottom = tab-h + 1rem + 44px + .5rem`) or the FAB hides while a toast shows; one toast at a time with the queue behind it.

**R-11 · Updated now / nod are timers in render state. P2 · S.**
- **What:** `performance.now()<st.nodUntil` evaluated during render; if nothing re-renders at expiry the nod class and "Updated now" stay. (read)
- **Fix:** Drive from the store: an `updated` flag with a timeout that clears it and re-renders only the status line.

**R-12 · Optimistic actions with rollback. P0 · M.**
- **What:** Publish, Disconnect, Revoke apply in the same frame and settle. None can fail; no rollback exists; the spec requires one for Publish ("removes the optimistic slip and says why"), and "Save failed" (§4.14) is a named state. (read)
- **Fix:** One `optimistic(action, undo, work)` helper: apply `action()`, run `work()` (a promise), on reject call `undo()`, append a failure event, announce once. Wire Publish (M-6), Replace reference (M-5), Rename (M-3), Settings saves (M-7), Disconnect and Revoke (fail path: "Couldn't remove that. Nothing was changed."). Each reachable with a reviewer control.

**R-13 · Settle on Memory rows, receipt stations and slips together. P1 · S.**
- **What:** `.settle` is set per service for the receipt and the Agent-view cards but the slip's chip and Memory rows in *other* services never settle, and the fact list row does not either. Spec §4.12: "affected rows settle". (read)
- **Fix:** Settle applies to every element carrying the changed fact id (`data-fact`), including the slip peek and the fact row.

**R-14 · Loading states. P1 · M.**
- **What:** Loading exists for: app frame (900ms), test (900ms), preview (800ms). Missing: route transitions, Settings sections, Memory, Connect Discover (the spec calls Discover "one bounded read"), and the first paint (a hash route renders synchronously, so there is no loading to see, which is also why X1's load error is unreachable). (read)
- **Fix:** Settings and Memory get the 300ms static loading state on first entry per session only (not on every visit). X1 "Couldn't load" gets a reviewer control ("Make the next screen fail to load") so it can be walked. Static Dot, one sentence, no spinner, no shimmer (spec §4.14 stays).

**R-15 · Progress. P1 · S.**
- **What:** Test "Testing…" and Preview "Fetching facts…" have no sense of how long. A stalled read has a permanent "Stalled?" link (always visible, from t=0) rather than appearing late. (read)
- **Fix:** After 3s the sentence extends: "Still reading. {n}s." (the n ticks; text only). The "Stalled? Open {App}" link appears at 6s, not at 0. After 10s, a real timeout state with Try again (M-6 pattern). Still no spinner. A determinate "Reading 2 of 3 facts" line in Preview when the count is known.

**R-16 · Offline does not do what the spec says. P0 · M.**
- **What:** On `offline` the code sets a flag, stops ticks and shows the strip. It does *not* "show states as Stale-with-time" (spec §4.14), and while offline `#live-toggle` can still be toggled to Off, so on reconnect the feed may stay off with the strip saying "Back online. Checking." (read)
- **Fix:** On offline: every Live fact is *displayed* as Stale with "offline" as its cause (not stored as Stale, so it restores cleanly); ages freeze. Pause button reads "Paused · offline" and is `aria-disabled`; the person's own live/pause choice is remembered separately and restored. On online: restore, re-check every Live fact once (timestamps update), message "Back online. Checked." Offline strip gets `role=status` content only through the single region (R-9), no second announcement.

**R-17 · Reconnect has no "checking" moment. P1 · S.**
- **What:** The strip goes "Back online. Checking." for 3s and then vanishes; nothing was actually re-checked. (read)
- **Fix:** Part of R-16. Strip shows "Back online. Checking." until the re-check resolves (600ms mock), then "Checked just now." for 3s.

**R-18 · Background retries with backoff. P1 · M.**
- **What:** None. A failed Test has a manual "Try again" (limit three); a refused frame has "Try again"; nothing retries by itself.
- **Fix (mock):** For a Needs-you/Unavailable *service*, Worlds retries its **read** quietly at 15s, 30s, 60s, 120s, then every 5 min (cap), jittered ±20%, and shows the line "Next check in 30s" (text; ticks down on the cadence). A manual "Check now" cancels the wait and resets the ladder. Backoff is paused while paused/offline. Nothing is ever sent beyond a read, and the owner link still stands in for "retry" (spec §4.8: Worlds has no retry button for owner retries). Do **not** add any retry for owner retries (`probe-provider`, `retry-last-job`): they stay links.

**R-19 · Pause/resume copy shows a stale age. P2 · S.**
- **What:** "Paused · frozen at 24s" is correct, but nothing says *how long* it was paused when resuming, and re-check timers resume from the frozen time so a pause of ten minutes yields no catch-up. (read)
- **Fix:** On resume: "Live feed on." (exists) plus, if paused > 60s, an immediate re-check of Live facts so ages do not jump from "frozen" to "stale" on the next tick.

**R-20 · Counters and badges. P1 · S.**
- **What:** Attention count updates correctly everywhere via `refreshAll`. Gaps: badge number unbounded; the nav badge's text is ", 1" for screen readers (fine) but the tab title never changes (M-15); Memory has no counts; the slip filter chips (M-13) need counts.
- **Fix:** Badge caps at "9+". Title prefix. Counts on filter chips. The status line pluralises ("2 need you", currently "2 needs you": `statusHTML` hard-codes "needs you"). (read)

**R-21 · State-word cross-fade is spec-only. P1 · S.**
- **What:** Spec §8.1: state word cross-fades 150ms. Code swaps the DOM via `innerHTML`, so there is no cross-fade; only `.settle` animates the receipt. (read)
- **Fix:** On a state change, the chip element keeps its node and swaps its text and glyph with a 150ms opacity transition (instant under reduced motion). Requires R-1's slice rendering.

**R-22 · Reduced motion gaps. P1 · S.**
- **What:** (a) `.fresh` Dot swap to the nod pose happens even when `--wv-dur-nod` is 0 (the pose image still changes for 1s). Spec: "no nod". (b) The `Carrying it over…` text and the lane appear for `dur+60ms` even at 0, a 60ms flash of the lane. (c) Toast uses `transform` with 0 duration (fine). (read)
- **Fix:** (a) Skip the pose change under reduced motion; keep "Updated now". (b) Under reduced motion go straight to the stamp state. (c) Test both the OS setting and "Reduce always" (the latter sets `data-motion` but `matchMedia` in JS only reads the OS flag in some places: unify in one `motionOK()`).

**R-23 · Live toggle and offline interact badly. P1 · S.** Part of R-16: remember the person's choice separately from the offline pause.

**R-24 · Cadence changes do nothing visible. P2 · S.**
- **What:** `cadence` changes `st.cadence` but the next repaint is whenever `sec % cadence` next hits 0; no feedback beyond the toast.
- **Fix:** Reset the modulo anchor on change; next repaint at `cadence` seconds from now.

**R-25 · Header toggle name includes churning data. P1 · S.**
- **What:** `#live-toggle` text changes every cadence ("Live · checked 24s ago" → "…29s…"), and it is also `aria-pressed`, so a screen reader hears state twice ("Live, pressed") and the name changes under focus. (check)
- **Fix:** Keep the checker's visible text but split: the button reads "Live" / "Paused" (with `aria-pressed`) and the age sits in an adjacent text node, not inside the button. This needs a spec edit to §11 (the checker reads `#live-toggle`'s text); flag to the spec owner rather than editing it here. Fallback if the text must stay: keep as is and add `aria-live="off"`.

**R-26 · `#simulate-change` is enabled when Front Door is not connected. P1 · S.**
- **What:** It toasts "Front Door isn't connected. Nothing to update." The spec's disabled-with-reason pattern (`aria-disabled` + visible reason) is for exactly this. (read)
- **Fix:** `aria-disabled="true"` with `aria-describedby` pointing at "Connect Front Door first"; keep it focusable.

**R-27 · Multi-event stale message loses events. P2 · S.**
- **What:** `stepFacts` returns one string; two facts going stale in the same second report only the last. (read)
- **Fix:** Return a list, batch the message ("Media Shelf and Notes Sync are now Stale.").

**R-28 · Stale/unknown never reaches the slip peek. P1 · S.**
- **What:** The slip shows `facts[0]` only. If the *first* fact is Live and the second is Stale, the slip reads healthy. (read)
- **Fix:** The slip's chip already uses the service state; add a small line "1 of 3 facts stale" whenever any fact's state differs from the service's. Terse: "1 stale." Stays text.

**R-29 · The status line's "checked Ns ago" is the *freshest*, not the *oldest*. P1 · S.**
- **What:** A reassuring number hides an old one. (read)
- **Fix:** Status line uses the freshest only for the Live label; add the oldest in the slip footer. For the counter: "Oldest: 3h" shown only when it differs from the freshest by more than an hour.

**R-30 · Frame load states are a timer, not a lifecycle. P2 · S.**
- **What:** `PLAN` hard-codes first-try failures for Front Door and Notes Sync, so the "loaded" path is only seen on the second click. A reviewer cannot see a first-try success for those.
- **Fix:** Reviewer control "Make the next frame fail: refused / slow / never" (a select), default none, so both paths are reachable on any service.

**R-31 · Pending states are time-based placeholders. P2 · S.**
- **What:** "Saving…" is 600ms regardless; test 900ms; preview 800ms.
- **Fix:** Randomised ±25% mock latency, and the "Simulate slow" reviewer control multiplies by 8, so B-8 (stalled states) is testable.

**R-32 · The Needs-you badge and attention count count *services*, not *facts*. P2 · S.**
- **What:** Front Door has three facts and one needs a decision, so "1 needs you" is right; with 20+ services the count can overstate. Fine for now.
- **Fix:** Leave; note in §12 as a Q for Rylee: count services or decisions?

---

## 3. Robustness

Edge cases and failure paths. Each: what happens now (read, or check), the fix.

### 3A. Input and double actions

**B-1 · Secret in the Replace field (Settings). P0 · S.**
- `ref-save` clears the field and shows the refusal; `Escape`, blur and Enter paths are handled; but the **`input` handler** (`rep-ref`) only shows "dirty" and never checks, so a pasted secret sits visible in the field until Save. The Connect field is validated on blur. (read)
- **Fix:** Validate Replace on blur like C2 and clear on detection. Never store `.value` in the store or event log. Add `autocomplete="off"` and `data-lpignore`-style attrs (already `autocomplete=off`). Also check pasted values on `paste` (clear on paste if it fails shape, before any render).

**B-2 · Reference field edge cases. P1 · S.**
- Unicode lookalikes, whitespace, zero-width characters, a very long string, and `ref://` with trailing slash are not tested; the regex rejects most, which is the safe direction, but the **message says "That looks like a secret"** for a merely malformed reference (e.g. `ref://notes sync`). (read)
- **Fix:** Two refusals: "Not a reference. Use ref://name." for malformed-but-harmless (keep the text in the field so it can be fixed; this is not a secret), and the secret refusal (clear) only when it fails a real secret-shape test (long, high-entropy, or token-prefix like `sk-`, `ghp_`, 32+ hex or base64 chars). Document the heuristic in the spec; it is a mock. Max length 49 chars after `ref://`, shown as live "n/49".

**B-3 · Double click / rapid activation. P1 · S.**
- `publish` is guarded by `phase`. `w-connect` is **not** guarded in `ACT` (it relies on the button being replaced by a synchronous render). `cx-run` guards `running`. `dlg-disc` can fire twice if Enter is held. `cx-next` on the Reference step can be triggered twice before `refState='pending'` repaints; the 600ms timer then runs twice and navigates twice, pushing two history entries. (read)
- **Fix:** One `once(key, fn)` guard keyed per action instance; set `aria-disabled` immediately and keep focus on the button (do not `disabled`). Ignore key-repeat (`e.repeat`) on activation keys for consequential actions (disconnect, revoke, publish).

**B-4 · Rapid toggling. P1 · S.**
- Live toggle: each press toasts and re-labels; fast toggling queues toasts (R-9) but state is consistent. Theme/motion radios: re-applied instantly, fine. Slip selection while an app frame is loading: the old frame's timer still runs and `paintFrame` targets `#frame-{id}` which may not be in the DOM; guarded by `getElementById`, fine. Cadence select with keyboard arrows fires a toast per option. (read)
- **Fix:** Debounce the cadence toast (wait 400ms); batch live toggles (last wins, one announcement).

**B-5 · Simulate change repeated / out of order. P2 · S.** See R-26 and M-20.

**B-6 · Scope and fact checkboxes at the last one. P2 · S.**
- C2 scope allows unticking all (the sentence says "Tick at least one." and Next disables); C5 and the welcome refuse the last untick silently (`t.checked=true`). Inconsistent: two behaviours for the same rule. (read)
- **Fix:** One rule: the last item is `aria-disabled` with its reason ("Keep at least one."), as spec §4.4 C5 says ("last-one-locked"). Apply it to C2 as well? The spec says C2 allows none → invalid. Keep C2's invalid state but make the welcome match C5.

### 3B. Every Connect step failing

**B-7 · Per-step failure table. P0 · M.**

| Step | Failure | Today | Needed |
|---|---|---|---|
| C1 Discover | read fails / no candidates | cannot fail | "Couldn't look. Nothing changed. Try again." + reviewer control |
| C2 Reference | secret, own secret, empty, malformed | handled (B-2 tweak) | Own-secret refusal also clears nothing and says why; **pending save fails** → "Couldn't save. Nothing was changed." |
| C3 Test | fails ×3 | handled, with generic cause (B-8) | Cause per service from the fixture `lastError`, plus a *timeout* ("Too slow.") and a *refused* ("Reference refused.") variant |
| C4 Preview | read fails / stalls / empty | only success; "Stalled?" is always on; the empty state is unreachable | Failure state with owner link, stalled state at 6s (R-15), empty state reachable via a zero-facts template |
| C5 Choose | nothing ticked | last is locked | fine |
| C6 Publish | fails | cannot | M-6 |
| Leaving mid-run | Back/Escape/hashchange during `running` | the 900ms timer still resolves and calls `say('Test failed.', loud)` for a screen the person left | cancel the timers on route leave; no announcements for abandoned work |

Add one reviewer control, "Make the next Connect step fail", with a step select, so every row is reachable.

**B-8 · Failed test cause is hard-coded. P0 · S.**
- `Provider timed out` is a literal in `viewConnect`; spec C3 says the cause comes from the fixture `lastError` ("provider timed out", "job rejected: no media loaded"). For services with no `retry`, there is no fixture error. (read)
- **Fix:** Use `s.retry.lastError` when present, else a small classed list ("Provider timed out.", "Reference refused.", "Unreachable.") chosen by the simulate control. Never free text from a provider.

**B-9 · Escape throws away a typed reference. P1 · S.** See M-27.

**B-10 · Browser Back during Connect. P1 · S.**
- `cxGuard` bounces forward routes to the earliest valid step with `replaceState`, so Back from Test after a pass can land on Reference → fine. But Back **into** `#/connect/test` while `t.state==='running'` re-renders a dead timer's result. (read)
- **Fix:** Cancel in-flight mock work on leave (B-7 last row).

**B-11 · Dialogs are not part of history. P1 · M.**
- Browser Back while a dialog is open navigates behind the modal; the dialog stays up over a different screen and its `dlgInv` points at an element that no longer exists, so focus restores to `#main h1`. (read)
- **Fix:** Close the dialog on `hashchange`, then run the route. Alternatively push a history state when a dialog opens (preferable on phone sheets; Back closes the sheet). Pick one; the sheet case is the common one.

### 3C. Re-render side effects

**B-12 · `refreshAll` wipes in-progress edits and focus. P0 · M.**
- Any stale/unknown event, simulate, Check now, mock control or "Updated now" expiry calls `renderView({})`, which replaces `#main`'s HTML. Effects (read): the Replace reference field (`#rep-ref`) loses its typed text (its value is not in state); an open Memory filter `<select>` collapses; the focus ring jumps via `keepFocus` only for elements with `data-fk` or an id (the Cancel/Reload buttons inside the frame, `dismiss-note`, `dismiss-journey`, `ref-save`, `ref-cancel` have neither, so focus drops to `<body>`); a screen reader in browse mode loses its place; the text caret in `#cx-ref` is not preserved; scroll is preserved by the browser only by luck.
- **Fix:** R-1 slice rendering is the real fix. Immediate stopgaps (S): (1) never re-render a view that contains a focused text input or open select, defer the repaint until blur; (2) give every button a stable `data-fk`; (3) store the in-progress Replace value; (4) preserve `selectionStart/End`; (5) save and restore `scrollTop`. With slices (M), only the changed nodes update.

**B-13 · Focus is lost after dismissals and inline panels. P0 · S.**
- Focus restoration audit (read):

| Action | Today | Should be |
|---|---|---|
| Close dialog | returns to invoker (good), fallback `#main h1` | ok |
| Disconnect confirm | next slip or `#add-service` (good) | ok |
| Dismiss last-change note | **body** | the next focusable thing in the note's place: the page heading |
| Dismiss journey note | **body** | the receipt heading |
| Replace → Save | **body** | the Replace button |
| Replace → Cancel | Replace button (good) | ok |
| Frame Cancel / Reload / Try again | repaint via `keepFocus`, but those buttons have no `data-fk` so **body** | same button, stable fk |
| Tab change | `data-fk=tab-x` (good) | ok |
| Filter select (Memory) | re-render, no fk on the select except id (works via id) | ok |
| Welcome → W2 | `focus:true` then heading | ok |
- **Fix:** `data-fk` on every control, plus a fallback "focus the nearest preceding heading" if the target is gone.

**B-14 · Keyboard trap check. P1 · S.**
- Native `<dialog>.showModal()` traps correctly and Escape closes. Possible trap: the dialog's *first focus* is the heading (`tabindex=-1`), so Shift+Tab from the heading goes to the last button (fine). The offline strip, toast and skip link are not focusable (fine). The rail tooltip (`::after` on `:focus-visible`) can cover the neighbouring control on tablet (visual only). (check)
- **Fix:** Verify in a browser: Tab/Shift+Tab through every screen at each width, in each of the four themes. Add the keyboard section to Help (M-18).

**B-15 · Tablist is not a tablist. P1 · S.**
- Phone tabs use `role=tablist/tab` with `aria-selected`, but all three tabs are in the Tab order, no arrow-key handling, no `aria-controls`, and the panes are unlabelled `section`s without `role=tabpanel`. (read)
- **Fix:** Roving tabindex (selected tab only focusable), Left/Right/Home/End, `role=tabpanel` + `aria-labelledby`, `hidden` on inactive panes (not just CSS) so screen readers skip them. Or drop the roles and use three buttons with `aria-pressed` (matches the rest of the app: slips and fact rows are `aria-pressed` buttons). Recommend the latter: smaller and consistent.

### 3D. Content extremes

**B-16 · Very long names. P1 · M.**
- Wrapping is global (`overflow-wrap:anywhere`), but: the desktop top bar's `#disconnect` text includes the name, a 60-character name overflows the sticky bar (`.controls` is a flex row); slip header `slip-top` is `flex` with the chip beside the name, a long name pushes the chip below or squashes; the tablet nav tooltip; breadcrumb-ish "Back to counter"; Settings row buttons "Disconnect {name}" are wide pills. (read for CSS; check for rendering)
- **Fix:** Cap display names at 40 characters (M-3). `#disconnect` label: `Disconnect {name}` on a single line with `max-inline-size: 20ch; overflow: hidden; text-overflow: ellipsis` **plus** the full name in `aria-label` and `title`. The exception to "never truncate" is documented: this is a button label with the full text one tab away. Everywhere else, wrap. Slip: `flex-wrap:wrap` with the chip allowed to wrap under the name. Test with: "Garden Camera, back lawn, left of the shed, the one that faces the road" (68 chars) and a single unbroken 48-char string.

**B-17 · Many services (20+). P0 · L.**
- Home: slips are a single column (23rem) or a two-column grid above a detail pane, with no search, no sort, no grouping, no sticky detail. At 1440 the detail pane sits beside a list that scrolls the whole page; at ≤75rem the list stacks *above* the pane, so choosing slip #14 changes a pane that is a full screen below the fold and nothing signals it. Memory renders every fact of every service (20 × 3 = 60 articles) with no collapse. Settings lists everything flat. Nav badge unbounded. The Discover list is long. (read/check)
- **Fix:** (1) Search/filter/sort (M-13, M-14). (2) Desktop: the slips column gets `max-block-size: calc(100dvh - top)` with its own scroll and `position: sticky`; the detail pane is sticky-top-aligned. (3) Tablet/phone-wide: selecting a slip scrolls the detail heading into view and moves a "Selected" mini-bar to the top of the viewport (sticky, one line, with the chip). (4) Group slips under state headings when > 12 ("Needs you · 2", "Healthy · 14") as collapsible `<details>` with the count in the summary; group order = sort order. (5) Memory: services are collapsible `<details>` with the heading as summary, open by default for ≤ 6 services, closed beyond. (6) Settings > Services gets the same search. (7) Test data: a "Make 24 services" reviewer control (clones templates) so this is checkable.

**B-18 · Zero facts. P1 · S.**
- Slip: "No facts / None" (ok). Receipt: "No facts" + emptyReason (ok). Fact list: absent (ok). Memory group: **heading with nothing**. Agent view: muted text. "Agent sees:" line: omitted (ok). Status line: counts the service as present (ok). A service whose facts are *all kept out* cannot exist (Choose locks the last). A fact with a `null` value and state `live` renders "Unknown" via `fs()` (`obs==null`) (read, ok).
- **Fix:** M-24 row for Memory; add the owner link to the zero-facts receipt.

**B-19 · Long values and many facts per service. P2 · S.**
- Fact value uses `overflow-wrap:anywhere` (good). A service with 40 facts shows 40 buttons in a list inside the pane with no cap; the `receipt` is below, off screen.
- **Fix:** Fact list scrolls inside a max-height (12 rows) with a "Show all 40" button; the selected fact's receipt follows selection, scrolls into view on selection when off-screen.

**B-20 · Fact value formatting. P2 · S.**
- Numbers use `toLocaleString('en-US')`; dates use UTC `fmtDT` with no zone label; units appended raw ("47 minutes", "4.2 GB"); `1 minutes` is possible for a plural unit (`unit` is a literal string, so `1 items`, `1 jobs`; the fixture's printer queue is 1 → "1 jobs"). (read)
- **Fix:** Pluralise by unit table (`items, jobs, notes, minutes`) via `pl()`; GB/s stay as is.

### 3E. Time

**B-21 · "2:23 PM" has no zone. P0 · S.**
- `fmtT`/`fmtDT` force `timeZone:'UTC'` and `en-US` and print "2:23 PM" with no zone. The only mention is "Times in UTC." in About. A person in another zone reads a time that is wrong by hours and nothing says so; spec §4.9 prints "since 2:23 PM" (also unlabelled). (read)
- **Fix:** Append " UTC" to every absolute time in the mock ("2:23 PM UTC"), or use the device zone with the abbreviation (see M-28). Relative times never need a zone. Dates older than today show the date ("Oct 9, 6:00 AM UTC"). `Intl` locale from `navigator.language`, with `en-US` fallback.

**B-22 · Nothing persists across reload. P0 · M.**
- `st` is in-memory. Reload returns to the welcome, forgets theme, motion, cadence and every connection, and re-arms the stale scripts. The spec says the welcome is "stored in the mock session" and that people expect their theme to stick. (read)
- **Fix:** `localStorage` only (no network): store `{v:1, theme, motion, cadence, timeMode, welcomeDone, journeySeen, instances:[{id, templateId, name, ref, scope, keptOut, connectedAt, during}], selected, memFilter, search, sort}`. **Do not store**: values entered in any field before validation, anything that failed the secret check, the clock offset, scripted stage state (restart the proof path on load; the clock restarts at the fixture time), the event log (session only). Version key `worlds-mock-v1`; on parse failure or version change, drop it quietly and start clean. "Start over" (M-20) clears it. Private browsing/blocked storage: catch, run in memory, no error shown.

**B-23 · The mock clock and the real clock disagree. P1 · S.**
- Mock time starts at the fixture's `generatedAt` (2026-10-13T14:24:26Z) regardless of when the page loads; on any later date the reviewer sees "2:24 PM" when it is 9 AM. That is intended for the mock; nothing says it. (read)
- **Fix:** About says it in one line: "Mock clock starts at 2:24 PM UTC on Oct 13. Real time isn't used." And `title` on the status line says "mock time".

**B-24 · Ages that cross boundaries. P2 · S.**
- `Math.round` for ages: 59.6s → "60s"? `shortAge(60)` returns "1m" (ok). `0s` → R-4. Negative ages clamp to 0 (ok). A `checkedAt` in the future (clock catch-up) clamps (ok).
- **Fix:** none beyond R-4; add a unit test of `shortAge` boundaries (0, 4, 5, 59, 60, 3599, 3600, 86399, 86400).

### 3F. Embed, offline, storage

**B-25 · Embed refused/timeout/slow, in one place. P1 · S.**
- Frame states exist (loading, loaded, refused, timeout, cancelled). Missing: "stuck loading" (no timeout from the loading state in the code besides the planned one); a *mid-session* failure (loaded then the app dies); frames never receive a `sandbox` attribute because the mock uses a div (spec Q4 UNKNOWN: fine, but the final build needs a note).
- **Fix:** Hard timeout at 8s → "Too slow."; "Reload" on loaded; reviewer control (R-30). Add a spec line that the real `<iframe>` must carry `sandbox` with no `allow-same-origin` and `referrerpolicy="no-referrer"`, and `credentialless`/`csp` where supported, as a build note (not a design change).

**B-26 · Offline mid-action. P1 · S.**
- Test/Publish/Replace while offline run as if online (mock). Real build would fail.
- **Fix:** While offline, actions that would call out are `aria-disabled` with the reason "Offline." (Test, Re-test, Publish, Replace). Navigation, Memory, Settings, Disconnect (local only) keep working. Disconnect offline is allowed and says "Offline. Removed from Worlds." because disconnect is Worlds-local.

**B-27 · Storage unavailable / corrupt. P2 · S.** Part of B-22.

**B-28 · Owner links in new tabs. P2 · S.**
- `<a href="app://home">` is intercepted on click only; middle-click, Ctrl/Cmd-click, "open in new tab", and drag try to navigate to `app://`, giving the browser's own error page. Spec: "no dead link". (read)
- **Fix:** Render as `<a href="#/owner/home">` (a real in-app route the prototype handles by opening the note) or `<button>`; keep the `app://` text visible in the note. Right-click/open-in-tab then lands on a Worlds screen.

### 3G. Accessibility, contrast, zoom

**B-29 · Screen-reader announcements. P1 · M.**
- Items (read): the single polite region is also fed by `say()` for *every* action including selection-less things; `#ref-msg`/test result/`#rep-msg` are separate live regions inside re-rendered DOM (unreliable); the slip's accessible name is its entire text (name, kind, chip, reason, peek, age, selected) read as one string with a changing age; spec §8.3 wants "Front Door, Needs you, checked 24s ago, selected". "Updated now" is visual only for the nod and is not announced (the toast covers it for simulate). Disabled `perm-none` buttons are `aria-disabled` and focusable (good).
- **Fix:** `aria-label` on each slip per §8.3 and `aria-describedby` pointing to the reason line; keep the age text out of the name where it ticks (use `aria-hidden` on the ticking span and put the age in the label only at render). One live region (R-9). Announce "Selected Front Door." on slip select (phone push moves focus; desktop does not, so it needs the message). Test with NVDA+Firefox, VoiceOver+Safari (iOS and macOS), TalkBack+Chrome.

**B-30 · Contrast in all four house modes. P1 · S.**
- Tokens pass (§8.5, measured from tokens). Not measured on the build. Specific risks (check): (a) the **chip glyph + word** for Stale/Unknown/Not configured in Low stimulation share one colour; the glyph shape must differ (it does) and the word is present; (b) `.micro.muted` text on `--surface-sunken` in Light (6.3:1, passes) but at `--type-small` the weight is 400, check legibility; (c) `aria-disabled` buttons: confirm the visual treatment of disabled is distinguishable from enabled in High contrast without relying on opacity alone (disabled text is exempt from contrast but must not become invisible); (d) mint `--accent-mint` MOCKUP label border 3:1 in Light; (e) the **toast border** `--status-done` against `--surface-base` in Light (needs 3:1); (f) **Dot's ink in Light** (spec §8.5 flags it).
- **Fix:** Run an automated pass (axe-core in a page test) plus a manual pass: 4 themes × 3 widths × {home, receipt, connect reference with error, dialog, offline strip, handoff}. Fix any token use, not by adding colours. Add `@media (forced-colors: active)` rules: keep chip glyphs and borders in `CanvasText`/`ButtonText`, rely on outlines (`outline` survives forced colours; `box-shadow` does not, so the FAB and toast need a real border; the toast has one, the FAB gets one).

**B-31 · 200% text / zoom. P1 · S.**
- Breakpoints are in rem (good). Risks (check): the sticky top bar uses `--wv-top-h: 4.5rem/7rem` fixed heights while its contents wrap taller at 200% text (at 320px width the bar's controls wrap to 3 rows), covering the first content (`scroll-padding-top` is also that fixed number); the phone tab bar `3.5rem` with four labels at 200% text; the FAB covers content at 200% (list bottom padding is `6.5rem`); `min-width: 20rem` on body at 200% means horizontal scroll at 320px (a 20rem body at 200% text-zoom is 640 CSS px of content in a 320px viewport: this is normal reflow behaviour only if nothing forces width).
- **Fix:** Make `--wv-top-h` a measured value (a `ResizeObserver` sets it) or use `position: static` below 40rem; use `min-block-size` not fixed heights; remove `min-width: 20rem` from `body` (use `min-width: 0` and let the layout reflow at 320); recheck FAB padding at 200%. Test: 320px wide, 200% text, each screen, no sideways scroll, no clipped controls.

**B-32 · 320px width. P1 · S.**
- Phone target is 390; 320 is not designed. Likely overflow (check): the receipt stations row, the slip header (name + chip), `.cx-bar` (Cancel, spacer, Back, Next in one row), tab bar labels ("Needs you" with badge), dialog sheet buttons, the Settings row (text + wide "Disconnect {name}" pill).
- **Fix:** Stack `cx-bar` to two rows under 24rem (Next full width on top); let buttons wrap their labels; tab labels `font-size: var(--type-micro)` is not allowed (micro is for the MOCKUP label only, spec §8.4), so abbreviate nothing and allow two-line labels; dialog buttons stack full width.

**B-33 · Focus never hidden behind sticky bars. P1 · S.**
- `scroll-padding-top` uses the fixed top height; `scroll-padding-bottom: 6rem` for the tab bar/FAB. When the top bar wraps taller (B-31) focused controls can sit behind it. (check)
- **Fix:** tie to the measured heights (B-31); add `scroll-margin` to every focusable in a list.

**B-34 · Skip link target. P2 · S.** The skip link goes to `#main` (focus), but on the phone the Settings header button comes before `main`, skipping nothing useful. Add a second skip link "Skip to navigation" only if the tab bar sits after `main` in the DOM. (read: it does.)

**B-35 · Language, title and landmarks. P2 · S.**
- `<title>` is static ("Worlds · MOCKUP") on every route; the page's `h1` changes. The rail and tab bar share `aria-label="Worlds sections"` (two `nav` landmarks with the same name, one hidden by CSS display so only one is exposed; fine). The offline strip is not in a landmark.
- **Fix:** Update `document.title` per route ("Memory · Worlds · MOCKUP", with the Needs-you count prefix, M-15). Keep one `nav` exposed per width (verify `display:none` removes the hidden one from the accessibility tree).

**B-36 · Security-shaped hygiene in the mock. P2 · S.**
- Template literals build HTML; everything user-influenced goes through `esc()` (name, ref). With rename (M-3) and search (M-13) that surface grows: a name like `<img src=x onerror=…>` must render as text everywhere including `title`, `aria-label` and the document title. (read: `esc` is applied consistently today.)
- **Fix:** Add a test page string table of nasty names (markup, quotes, RTL override, zero-width, emoji ZWJ) and view them on every screen; set `document.title` via `textContent`.

---

## 4. Polish

### 4A. Consistency and the token ladder

**P-1 · Off-ladder spacing, against the spec's own rule. P1 · M.**
- Spec §6: "No colour, gap, radius or text size is written as a literal outside tokens or the local handles." The prototype CSS has about 40 `rem` literals for padding, margin and gap that are not `--space-*`: `.4rem .8rem`, `.6rem var(--space-md)`, `.65rem 1rem`, `.5rem .75rem`, `.3rem .7rem`, `.2rem .45rem` (the MOCKUP label), `.35rem` (global `p` margin), `.15rem`, `.1rem`, `1.1rem`; plus inline `style="…gap:1rem…"` in five places and `font-size:var(--type-h1)` inline on six headings. (read)
- **Fix:** Snap each to the ladder: `.1–.2rem` → `--space-xs`; `.3–.5rem` → `--space-sm`; `.6–1.1rem` → `--space-md`. Where the ladder is genuinely too coarse (the MOCKUP label's `.2rem .45rem`), add two local handles `--wv-pad-tight` (`.125rem`) and `--wv-pad-chip` and list them in §6, rather than leaving literals. Move every inline `style` to a class (`.stack`, `.row-center`, `.h-sub`). Run a script check ("no `rem` literals in padding/margin/gap outside `:root`") in CI; this is the spec's own rule and needs a test.

**P-2 · Heading ladder is inconsistent. P1 · S.**
- Section headings inside views (`Owner retries`, `Proposals`, `Already connected`, service names on Needs you and Memory) set `font-size: var(--type-h1)` inline, while the spec defines `--wv-display-section` (1.85rem) for section headings and CSS sets `h2` to it. The inline overrides shrink them to 1.5rem, so the display-to-body step the spec calls the "printed, hand-labelled" air is quieter than intended exactly where a person scans most (Memory, Needs you). (read)
- **Fix:** Decide the ladder once, with a table: page title `--wv-display-page`; section `--wv-display-section`; *card/service title inside a list* `--type-h1`; slip name `--type-lead`. Apply by class (`.h-card`), remove the inline styles, and add `.h-card` to §6.

**P-3 · Duplicated selected-service header on phone/tablet. P2 · S.**
- `selCard` ("Selected / name / chip / reason / Open / Disconnect") appears above the grid on phone only (hidden by CSS on wide screens); on tablet it is also hidden, but the tablet layout also lacks the one-glance selected card the spec describes for phone only. OK per spec; but on phone the same service name then appears again as the pushed screen's `h1`. Fine. Note only that on desktop `#disconnect` lives in the top bar while on phone it lives in the card, so its position differs by width by design. (read)
- **Fix:** none; confirm `#disconnect` is never present twice in the DOM (it is moved by `placeControls`, good).

**P-4 · Chip glyph sizing and baseline. P2 · S.** Chips use inline 16px-viewBox SVG with `stroke-width 1.7`; the nav icons use 20px viewBox with the same stroke; at 20px the nav glyph reads thinner than the chip glyph. Set stroke by `vector-effect` or per-size stroke so optical weight matches; align the chip text baseline (`align-items:center` + `line-height:1`). (check)

**P-5 · "(simulated)" suffix appears after every chip and reads as a wall of text. P2 · S.** Repeated on the slip, fact row, receipt, Memory row. Replace with a small lilac "sim" pill with the full word "simulated" in `title` and visually-hidden text; keep the word visible once per card in the receipt. Spec says every feed-driven change carries "simulated": one visible instance per card satisfies it; the others become the pill with sr-only text.

**P-6 · Button hierarchy. P1 · S.**
- Three primary-looking things per screen on some pages (receipt "Check now" is secondary; "Open Home app" is primary on Needs you and "Ask Project Home to review" secondary: good). On Connect the sticky bar's Next is primary and the step body can also hold a primary (Run safe test is primary until it passes, then Next is also primary): two mint buttons at once. Danger buttons ("Disconnect" in the top bar) are always visible at the same weight as "Add service". (read)
- **Fix:** One mint button per view: Run safe test is secondary once it has passed; the top bar `Disconnect` is a text-weight danger on desktop (border only on hover/focus) so it does not out-shout `Add service`. Keep 44px targets and `--status-failed` colour; the word stays.

**P-7 · Alignment of the top bar on desktop. P2 · S.** Controls are one flex row after the brand with `margin-left:auto`; at 75–90rem the four controls plus a long live label ("Paused · frozen at 24s") crowd the brand; tablet uses two rows. Fix: fixed widths for the live toggle (`min-inline-size: 16ch`, tabular-nums for the age so it does not jitter every 5s).

**P-8 · Number jitter. P2 · S.** Ages tick in a proportional font so "checked 9s ago"→"14s" shifts text. Add `font-variant-numeric: tabular-nums` to `[data-ak]` and the live label.

**P-9 · Fact row vs slip peek duplicate vocabulary. P2 · S.** The slip peek prints `(last known)` in bold after the value, the fact row prints a separate micro "last known" under it. Use one construction: value, then a micro "last known" line, in both.

**P-10 · Rail footer and tablet rail. P2 · S.** Settings sits at the rail foot (spec) but on tablet the narrow rail (5.5rem) wraps "Credential…"; confirm labels fit (Home, Connect, Needs you, Memory, Settings) at 200% text, where "Needs you" wraps to two lines and the badge overlaps. Give the badge a fixed corner position (top-right of the icon) rather than inline. (check)

### 4B. Motion timing

**P-11 · Timings are all spec-true; three are too quick or too long in context. P2 · S.**
- Receipt settle: 3 stations × 60ms + 150ms = 330ms total, fine. Stamp "lands" in 200ms (`--wv-dur-nod`) but it is *the proud moment*: it reads as a flash. Give the stamp its own `--wv-dur-stamp: 280ms` (scale 1.35→1 then a 40ms settle), spec §8.1 says 200ms: propose the change to the spec, not a silent override. Dot nod 200ms is a quick blink; an `ease-out` rotation over 200ms ×1 is what the spec says; leave.
- The loading placeholders are 800–900ms with no variation (R-31).
- **Fix:** propose `--wv-dur-stamp` to Rylee as a spec edit; leave others.

**P-12 · Dialog/sheet entrance. P2 · S.** The `sheet` keyframe (translateY 1rem + fade) is used for both the centred desktop dialog and the phone bottom sheet; the sheet should rise from the bottom edge (translateY 100% → 0 over 200ms), the dialog should fade+lift 1rem. Under reduced motion both instant.

**P-13 · Page transitions. P2 · S.** Route changes are instant swaps (spec §8.1: "Step change in Connect: content fades 150ms"). Prototype does not fade Connect steps. Add a 150ms opacity `tick` on `.cx-body > *` on step change (instant under reduced motion).

### 4C. Hierarchy and layout

**P-14 · Receipt is the hero but is not visually the hero. P1 · M.**
- Spec: "That receipt is the daily hero." In the prototype the receipt sits under the fact list, and the fact list rows are the same size and weight as slips. On desktop with a selected service the eye lands on the slip column and the header, not the receipt. (check)
- **Fix:** Give the receipt `--space-xl` padding, the `--border-line-strong` 2px frame (already) and a larger value line in `--type-h1`; fact list rows get a lighter border (`--border-line`) so the hierarchy reads slips → receipt → facts. Keep depth-by-surface (no shadow).

**P-15 · Empty well sizing. P2 · S.** `.empty` uses `grid-template-columns: auto 1fr` with a 17.5rem scene; on narrow desktop (60–75rem) the text column is narrow and the art tall. Cap the art at 40% of the well and let the text keep ≥ 28ch.

**P-16 · Status line hierarchy. P2 · S.** "1 needs you · checked 24s ago": the count word is coloured (apricot) but is the same weight as the rest. Bold the count word only (700, as state words are); keep it one line, wrap under at 320px.

**P-17 · Memory's per-fact card is heavy. P1 · M.**
- Each fact is a two-column article repeating source, scope, permission lines and reasons; for 3 services × 3 facts that is nine tall cards, no density control.
- **Fix:** Collapsed by default to one row (label, value, chip, age) with a disclosure for source/scope/permissions (B-17 collapses services). Unknown rows start expanded (they carry "what would help").

**P-18 · Settings rows. P2 · S.** Rows use a flexible two-column layout; "Disconnect {name}" pills are as heavy as the Replace/Remove pair. Use the same text-weight danger as P-6 and a consistent order: Rename · Test again · Replace · Remove.

### 4D. Dot: where Dot appears, and where Dot stays quiet

Spec rules (§1 item 6, §4.0): Dot rests beside the freshness line on Home, Connect, Memory, Settings; asleep on empty states; nods once on a state-word change; carries the parcel on publish; **quiet** on Needs you items, N2, D1, R1.

**P-19 · Where the prototype diverges. P1 · S.**

| Place | Prototype | Spec | Verdict |
|---|---|---|---|
| Needs you page header | `pageHead()` shows Dot (rest) beside the freshness line | "No Dot on item cards. Dot rests only on the empty state." | **Drift.** Remove from the header when items exist; keep on the empty state. |
| Connect (all steps) | No page header, no Dot, no freshness line | Dot rests in the Connect header | **Missing.** Add the freshness header to Connect. |
| Stale service header | `dot('curious')` beside the chip | Not in the spec. "Dot's face and pose never say whether something is good or bad." | **Drift, judgement call.** A curious Dot beside a Stale chip leans "worried". Recommend removing; Dot stays quiet on problem states. Ask Rylee only if they want it kept. |
| After disconnect | `dot('goodbye')` in the last-change note | D1 is quiet; "Dot falls asleep only when the counter becomes empty" | **Drift.** Either amend the spec (goodbye Dot in the *note*, not the dialog) or limit goodbye to the empty counter. Recommend: keep it, because it is warm and sits outside the dialog; say so in D1. Needs the owner's nod since §1 item 6 is a protected rule. |
| Test running / Preview loading / Frame loading | Dot (rest) beside the sentence | "static, awake" | Matches. |
| Welcome | asleep → welcome → hero → nod | matches | OK. |
| Memory empty / Needs-you empty | `dot('asleep','lg')` | matches | OK. |
| Settings | Dot rests in the header (via `pageHead`) | matches | OK. |

**P-20 · Dot quiet list (add to the spec). P1 · S.** Dot never appears on: error and refused states (reference refused, secret refused, failed test, failed publish, load error), the handoff panel, revoke, any assertive announcement, the offline strip, destructive confirms, and Reviewer controls. Exceptions that stay: load error and offline use a *still* Dot only in the full-page well (X1 says "Dot rests"), never in the strip or a toast. Write it as a table in §1 so reviewers can audit it.

**P-21 · Dot's size is a half-step too big in two places and soft on high-density screens. P1 · S.**
- Sources are **224px wide** WebPs (Dot) and rendered at `height: 4.75rem` (rest, about 64×76 css px) and `height: 10rem` (`.dot.lg`, 160px tall ≈ 216px wide). The `lg` render is near 1:1 at 1× and **2× upscaled (soft)** at 2×/3× phones; the hero (720px source) is fine; the stamp (160px at 2.5rem=40px) is fine. (read: pixel sizes from the files.)
- **Fix:** Regenerate the six Dot poses at 448px wide (retina), same prompts and base reference (provenance file lists the sources), or cap `.lg` at 7rem. Keep WebP, keep alpha. This is "art gap 0" below: a re-render, not new art.

**P-22 · Dot in the header on every page is the same still Dot. P2 · S.** It is correct (rests), but at 4.75rem tall beside a one-line freshness it makes the header 76px tall on every screen; at phone width it pushes content down. Use 3.25rem in `.fresh` on phone and 3.75rem on tablet; `lg` Dot only in wells and the welcome.

**P-23 · Where Dot could add warmth without breaking the rules. P2 · M. (proposals, owner's call)**
- The first time a slip reaches Healthy after being Needs you (the quiet calm, §1 item 9): Dot nods once beside "Nothing needs you." (existing behaviour on simulate, keep and extend to a genuine owner-reported change in the event log.)
- Undo after disconnect (M-17): Dot carries the parcel **back** (the existing `dot-parcel` mirrored with `transform: scaleX(-1)`; no new art).
- About/Help header: Dot welcome (existing `dot-welcome`).
- A "peeking" Dot for no-search-results (NEW ART).
- A tucked-in Dot for offline (NEW ART), only in the full-page "couldn't load" well.

### 4E. Icons, art placement and sizing

**P-24 · Service icons: no fallback, inconsistent heights. P0 (with M-1) · S.**
- `sico(id)` returns `''` for any id without art, so a renamed or second-instance service shows **no icon** and the name shifts left, breaking slip alignment. Icon sizes: `2rem` slip, `1.75rem` Discover, `2.5rem` service header, `2.25rem` brand; the sources are 112px wide with differing heights (93–134px), rendered `height: N` so widths vary and optical weight differs (the backup icon is the tallest at 134, so it reads biggest).
- **Fix:** One fixed square box per size (`.sico { inline-size: 2rem; block-size: 2rem; object-fit: contain }`), instance icons look up by `templateId`, with a generic icon fallback (NEW ART 1). Snap sizes to two: `--wv-icon-sm` (2rem) and `--wv-icon-lg` (2.5rem), and use only those.

**P-25 · The stamp. P2 · S.** The stamp (160×157) is placed beside Dot; at phone width it stacks above Dot and the tilt clips against the card edge (rotated bounding box). Add inline padding equal to the rotation overhang (`--space-sm`) and test at 320px.

**P-26 · The nav uses plain line icons, the house has painted sticker icons. P2 · S.** Spec: "may be used for nav in production at 20px+ beside their label". Not in this round unless the owner wants it; the line set is consistent with the chip glyphs. Note only: the nav icons are 20px with 1.7 stroke; confirm optical match with the 16px chip glyphs (P-4).

**P-27 · Art alt text and decorative rule. P2 · S.** Every image is `alt=""` + `aria-hidden` (good, decorative). The stamp's sentence ("Connected") is real text beside the image (good). Check the `hero-welcome` at 200% text on phone: fixed `13.75rem` width may crowd the copy column (check).

**P-28 · Copy polish in the terse-warmth voice (proposals; all new strings). P1 · S.**
Rules from the spec: fragments, no exclamation marks, no filler, state words fixed. Proposed strings for the new pieces:

| Where | String |
|---|---|
| Search placeholder/label | "Find a service" · result "3 of 12." · none "No matches." / "Clear filter" |
| Activity empty | "Quiet so far." |
| Activity row | "2:31 PM UTC · Front Door · Back door locked. Home reported it." |
| Undo/reconnect | "Notes Sync's gone from here. Back in one tap." / "Put it back" |
| Recently disconnected | "Nothing held." |
| Rename | label "Name" · "Renamed to {name}." · empty "Kept {name}." |
| Re-test | "Test again" · "Passed. 3 facts read. Nothing changed." |
| Failed publish | "Didn't publish. Nothing was added. Try again." |
| Offline action | "Offline." (as the reason beside any disabled action) |
| Back online | "Back online. Checked." |
| Away | "Away 4m. 1 thing changed." |
| Backoff line | "Next check in 30s." |
| Replay | "Replay. Nothing changes." |
| Reset | "Start over" / "Clears this browser's mock. Nothing else." |
| Slip filter | "Needs you 2" · "Stale 1" |
| Escape guard | "Nothing saved yet. Escape again to leave." |
| Help | "What's a reference? A name for a secret kept elsewhere. Worlds keeps the name only." |

### 4F. Art gaps: NEW art (max 6, in Dot's existing style)

Same generation path as the rest (`offload image`, flat #00FF00 backdrop keyed to transparent WebP, approved base Dot as `--ref`), 2x size (448px wide for Dot poses, 224px for icons), added to `PROVENANCE.md`.

1. **`icon-generic-service`**: a small blank paper slip or tiny parcel with a ribbon and no marking, apricot and mint line art, for any service without its own icon (renamed, second instance, user-added). Required by P-24.
2. **`dot-peek`**: Dot peering out from behind a small round magnifier, one eyestalk tilted, shell visible. For "No matches." and empty filters (M-24). Neutral expression; no worry, no delight.
3. **`dot-tucked`**: Dot with eyestalks drawn in and shell pulled down over the body, a single small unplugged-cable curl beside. Offline and "Couldn't load this." wells only (X1). Calm, not sad.
4. **`dot-shrug`**: Dot with eyestalks angled opposite, a tiny question mark in the shell spiral negative space. "Couldn't save that" and load error, where the words carry the meaning and Dot looks unbothered. (If budget forces a cut, share `dot-tucked` for both and drop this.)
5. **`empty-tray`**: the counter scene (as `empty-counter`) with a tidy empty tray and a small silent bell under a cloth. For Needs you empty, "Nothing needs you." Quiet and tidy; Dot is **not** in it (this is a quiet surface).
6. **`empty-ledger`**: a small open ledger book with a ribbon and nothing written, apricot and mint, for Activity empty and Recently disconnected "Nothing held."

Re-render, not new: the six Dot poses at 2x (P-21). Reuse, no art: parcel hand-back (mirror `dot-parcel`), Help header (`dot-welcome`).

---

## Appendix: open questions this audit raises (for Rylee, not blockers)

1. **Dot on a Stale service (P-19) and Dot goodbye after disconnect.** Remove the curious Dot; keep or remove the goodbye in the note? Recommend: remove curious, keep goodbye outside the dialog. These touch protected rule §1 item 6, so they need a yes.
2. **Stamp duration** (P-11): allow a slightly longer 280ms for the proud moment?
3. **Live toggle text** (R-25): split the age out of the button, changing the checker contract (§11)?
4. **Settings as pushed screens on phone** (M-8) instead of one long column?
5. **Counting** (R-32): does "needs you" count services or decisions?
6. **In-session undo window** (M-17): 30 minutes of mock time acceptable, given the open "Keep history after disconnect" decision stays untouched?

## Appendix: acceptance for the round

- A page test (one HTML file, no network) asserts: no `rem` literals in padding/margin/gap outside `:root`; no inline `style` with a length; `shortAge` boundaries; the refusal never echoes the secret into the DOM or storage; one `role=status` region; every `data-act` button has a stable `data-fk`; the proof path (§10) end to end including offline, reload and 24 services.
- Browser pass: keyboard-only, 390px and 320px, 200% text, four themes, reduced motion (OS and "Reduce always"), NVDA/VoiceOver on Home, Connect, a dialog, and the offline strip. Record results in the spec's Q9 row.
