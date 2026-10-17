# Worlds vNext: the full design (MOCKUP spec)

Status: MOCKUP. This is a design, not an approved product and not deployed. It describes screens and behaviour; it contains no code. Data is the synthetic `docs/vnext/fixture/fixture.json` only. Where this spec shows something the fixture does not contain, it says so and marks it as a sample or UNKNOWN.

## 1. The feeling to protect

Rylee's words: "comprehensive but also keep the original feeling", clarified as protect the feel, the look, the whimsy and the love, **not the copy**. This section is a review criterion for every later section. If something added below makes Worlds look like a generic admin console, it is wrong, however complete it is.

Sources studied: V2's `DESIGN.md` and `index.html` (the look as built: Mulberry & Mint), and Concept 5's `DESIGN.md` and `index.html` (where Dot, the stamp and the parcel were first drawn). Concept 5 was skinned in Wise lime and heavy type; that skin is **not** what Rylee picked. V2's Mulberry & Mint skin is. Where the two disagree, this spec follows V2's look and Concept 5's gestures.

### What makes it feel the way it does

**The look**

1. **A plum room with mint and apricot in it.** Everything sits on the three plum surfaces (`--surface-base` page, `--surface-raised` slips and cards, `--surface-sunken` wells and rails). Mint (`--action-primary`, `--accent-mint`) is the one thing to act on. Apricot (`--accent-apricot`, which is also the "needs you" colour) and lilac are accents, never fills. Seen in V2: the top bar, rail, slips, receipt, and the primary pills.
2. **Soft, round, paper-like shapes.** Slips and cards use `--radius-lg`; buttons and chips are full pills (`--radius-full`); inner wells use `--radius-md`. The receipt has a 2px `--border-line-strong` frame like a printed slip; empty states use a dashed `--border-line-strong` outline, like a space waiting for something. V2: `.slip`, `.receipt`, `.empty`, `.welcome`.
3. **Depth by surface, not by effect.** No gradients, no glow, no heavy shadows. Depth is the surface ladder plus a small lift: a slip rises about 2px and its border turns mint on hover or selection (150ms). Shadows exist only on things that float: the phone add-service button and the toast. V2: `.slip:hover`, `.fab`, `.toast`.
4. **Young Serif for the voice, Atkinson Hyperlegible Next for the reading, and a real size step between them.** The serif on headings gives the counter a printed, hand-labelled air; most of that air is the jump in size between the display face and the reading face (V2 built about 2.5:1 at page level). The body face keeps it readable. V2: every `h1`/`h2`/`h3`. §6 keeps this step with two product-local display handles.

**The counter and the slips**

5. **Worlds is a service counter.** "Your counter" holds one **slip** per service: name, kind, state word, one-line reason, one peeked fact, "checked 24s ago". You pick a slip and open its **receipt** (Source → Worlds → Agent / Human), three small sunken stations inside a framed card. That receipt is the daily hero. V2: `.slips`, `.receipt-stations`; Concept 5: `.st` stations.

**Dot, and how Dot behaves**

6. **Dot the snail is a small accent, never a gate and never the data courier.** Dot is drawn in line art with a spiral shell and eyestalks (Concept 5 `dot()`; V2's flatter apricot-shell, mint-body version). Fixed rules, taken from both concepts:
   - **Asleep** (closed eyes, a small "z") when the counter is empty: first run, after the last service is disconnected, empty lists. Concept 5 `dot('asleep')`, V2 §6.
   - **Nods once** (200ms) beside "Updated now" when a service's state word changes. Never on a plain tick. Concept 5 `.dot-nod`.
   - **Carries the parcel** across when a service is published (400ms desktop, 300ms phone). V2 `dot(true)` carries a slip; Concept 5 `dot('parcel')` carries a ribboned parcel.
   - **Rests** beside the freshness line in the header of every working screen (Home, Connect, Memory, Settings), still.
   - **Settles** beside "{Name} is here." after the stamp (`dot-settled`), and **says goodbye** in the note after a disconnect (`dot-goodbye`, outside the dialog), carries the parcel **back** on Undo, **peeks** when a search finds nothing (`dot-peek`), and **tucks in** only in the full-page "couldn't load" and offline wells (`dot-tucked`). A curious Dot (`dot-curious`) sits beside the chip of a Stale service.
   - Dot's face and pose never say whether something is good or bad. The words say that. Dot is quiet on every error, refusal and consequential surface (see DotMood in Reactive components for the list).

**The delight moments (the whimsy and the love)**

7. **The "Connected" stamp.** A tilted (about -4°) stamp in Young Serif capitals with a check lands beside Dot when a connection completes. Concept 5 `.stamp`, kept in V2 §11. It is the one flourish allowed to be a little proud.
8. **The parcel hand-off.** The Publish step is not a spinner; Dot walks the parcel to the counter and the new slip appears. Concept 5 `phase === 'delivering'`.
9. **The quiet calm.** When nothing needs a person the counter says so in one plain line and Dot rests. No confetti, no streak, no score. V2 `home()` status line.
10. **The receipt settling.** When a fact changes, the three stations tick in order, Source then Worlds then Agent / Human, 60ms apart. It is the counter showing its work. V2 `.station.updated`, Concept 5 §15.
11. **Kind small print.** Care shows up as a provenance line ("Connected in first run · reference only, never the secret"), as the service-drop line, and as "Worlds locked nothing." They sound like a person who understands what is happening wrote them. The wording is free to change; the habit of saying them is protected.

**The pacing**

12. **An unhurried, skippable welcome, one thing at a time.** V2 opens on a single broad welcome card with a sleeping Dot, one invitation and one button, with "Skip welcome" always available; it earns its way to the counter one connection at a time, with Dot carrying each slip across. Nothing is a tour you must finish.

**The motion character**

13. **Gentle, one curve, and only to confirm.** One easing, `cubic-bezier(.2,0,0,1)`. Motion confirms a change that has already happened; nothing moves on a routine tick except the age number. Under reduced motion the same moments become opacity-only or instant, and data never stops. V2 §11.

### How to use this section
- **Copy is not protected.** Every string in §7 is rewritten for clarity using `docs/vnext/house/LANGUAGE.md` (machine truth, then plain words, then optional voice).
- **Coverage must not flatten the feeling.** §4.0 carries a per-screen table naming which of items 1-13 each screen keeps, so the rule can be audited. Every working destination (Home, Connect, Memory, Settings) names at least one gesture from items 5-13 beyond the shared look. Where a screen is consequential (Needs you, disconnect confirm, revoke confirm, reference refused) it is deliberately *quiet*: no Dot, no flourish. `JOY-CURIOSITY-AND-CARE.md` says operational and consequential surfaces may be very quiet, and gifts are not toll booths.
- **Ignorable.** A person can ignore every flourish (Dot, stamp, parcel) and finish every job.

## Voice: terse warmth

Rylee (2026-10-13): "the prose to be reduced down to just… terse warmth?" The rule for every visible string, aria-label and announcement:

- As few words as possible while staying kind. Short sentences or fragments. Warm, not cute. No exclamation marks, no filler ("Worlds will…", "This means that…").
- Keep every honest fact: source, freshness, who can see, who can act, what is kept, what goes, fail-closed approvals, proposals can't run.
- State words stay exactly as `LANGUAGE.md` has them (Healthy, Needs you, Stale, Unavailable, Unknown, Not configured). Warmth never invents a state.
- A fact says Live only with a real checked time ("checked 12s ago"). Never checked means Unknown.

| Before | After |
|---|---|
| Nothing at the counter yet. Connect a service and Worlds will keep its facts, say where each came from, and leave the deciding to you. | Quiet here. Connect something? |
| Media Shelf's 3 facts and its app frame are removed from Worlds. The Media app is untouched. Its reference is kept. | Media Shelf's gone from here. The app's fine. Reference kept. |
| Passed. Worlds read 3 facts in 257ms (simulated). Nothing on Media Shelf was changed. | Passed. 3 facts read. Nothing changed. |
| Worlds can't send this to Project Home yet, so nothing was sent. You can decide in the Home app instead. | Nothing sent. Decide in the Home app instead. |
| You're offline. Worlds is showing what it last knew, marked with when. | Offline. Showing what was last known, with times. |

## Refinement round 1: checklist

Rylee (2026-10-13): "I love this. Let's send back for one round of refinement and to get every additional piece down and all the reactive elements we might need. Please. I'd like this to be a little robust and polished along with our whimsical snail."

One merged, de-duplicated list from two independent audits (`refine-audit-minimax.md` = **MM**, `refine-audit-sonnet.md` = **SN**) plus the Field Guide skeleton. The look, Dot and the warmth are protected (§1); nothing below changes them. Each line: `ID · what · where · fix (size) · source`. Sizes: **S** under half a day, **M** about a day, **L** several days or touches the store. Source names the audit and its own item number, so either audit can be searched. **P0** marks what breaks a spec rule, a trust rule (§10) or accessibility. Build order: store first (RX-01, RX-10, MP-01), then P0 correctness, then the missing screens, then polish. Every item is reflected in the sections below; the prototype round is checked against this list.

Claude's calls on the audits' open questions (each keeps the protected feeling): keep Dot curious beside Stale, and Dot's goodbye after disconnect; the stamp may take 280ms; `#live-toggle` keeps its id and its age text may sit beside it; phone Settings may be pushed screens; "needs you" counts decisions; in-session undo after disconnect lasts 30 seconds of mock time with a visible "Undo", and "Keep history after disconnect" stays open.

### Missing pieces

- [x] MP-01 · Services are fixed fixtures, so two of a kind, or a named one, can't exist · Discover, slips, routes, Settings · split kind template from instance (`instanceId`, `templateId`, `displayName`); ids `media-shelf`, `media-shelf-2`; Discover always lists templates with "Already connected ×n"; everything keys off instance id; existing checker ids stay (L) · both (MM M-12, SN M-1)
- [x] MP-02 · P0 · A fact's own state is invisible on the counter when it differs from the service word (Notes Sync starts Unavailable, so its Stale and Unknown never show) · slip, header, receipt · slip peek carries the fact's chip and "last known"; a line "1 stale." appears whenever any fact differs from the service word; the service word stays the service word; acceptance step 2 then works on a connected Notes Sync (M) · both (MM M-01, SN R-28)
- [x] MP-03 · The fixture's sentence vanishes on a simulated Stale or Unknown · service lines · summary first, simulated line under it, branch on the fact's state (S) · MM M-02
- [x] MP-04 · P0 · No "Replace reference" on a refused service · service header, slip, Source station · button starts Connect at Reference with an empty field; "Open Memory app" beside it (S) · both (MM M-03, SN M-2)
- [x] MP-05 · P0 · Replace in Settings never re-checks and never clears the refused flag · Settings > References · one path for Settings and Connect: validate, "Saving…", clear refused, run the safe test, then Live with a real checked time, or keep the old reference and say why (S) · both (MM M-04, SN M-5)
- [x] MP-06 · No way to re-test a connected service · reference rows, Source station · "Test again" opens the C3 panel inline; a pass sets checked times; three failures mark it Unavailable "Didn't go through." (M) · SN M-4
- [x] MP-07 · "Check now" only exists on the two scripted facts · fact row, receipt, Memory · show on any non-Live fact; add per-fact `changedAt` so the Source station says "checked 24s ago · changed 9m ago" (metadata only, not history) (S) · MM M-05
- [x] MP-08 · P0 · Publish can't fail, so rollback is undemonstrable · C6, For reviewers · "Make the next Publish fail": slip appears, leaves 900ms later, Connect returns to Publish with the reference and chosen facts kept, "Didn't publish. Nothing was added. Try again." (assertive once) (S) · both (MM M-06, SN M-6)
- [x] MP-09 · P0 · Only Test can fail in Connect · C1-C6, For reviewers · "Make the next Connect step fail" with a step select; per-step table in §4.4; reference and facts survive, Back works, nothing saved until Publish (M) · both (MM M-22, SN B-7)
- [x] MP-10 · Zero-fact services are unreachable, so three empty states are dead code · Settings > Providers · list every template with no instance (Local Weather) as "Not configured" with a "Connect" link that opens Connect with it preselected; the normal flow then reaches C4 empty, receipt "No facts", slip "No facts" (M) · both (MM M-07, SN M-23)
- [x] MP-11 · No rename · service header, Settings row · inline field "Name", up to 40 with live "n/40", Enter saves, Escape cancels, empty keeps the old name ("Kept {name}."), updates every view in one pass, announces "Renamed to {name}." (M) · both (MM M-11, SN M-3)
- [x] MP-12 · Kept-out facts can't be brought back · "kept out" line · "Change what's shown" reopens C5 with the current ticks and names the kept-out facts; Save applies in one pass (M) · SN M-11 Built as an inline panel in the service view that reuses the C5 list.
- [x] MP-13 · A scoped reference's scope can't be changed · Settings row · "Change scope" on every reference row opens Connect at Reference with the capabilities ticked; the test re-runs on save (S) · both (MM M-23, SN M-21)
- [x] MP-14 · No search or filter · Home (shown once more than 6 services), Memory · "Find a service" by name, kind, owner, fact label; state chips All · Needs you · Stale · Unavailable · Unknown with counts; "3 of 12." once; empty result is a dashed well with `dot-peek`, "No matches.", "Clear filter"; Memory filters fact rows inside its service select (M) · both (MM M-09, SN M-13)
- [x] MP-15 · No sort · Home · "Needs you first" (default), Name, Recently checked, Newest; DOM order = visual order; Dot does not react (S) · both (MM M-10, SN M-14)
- [x] MP-16 · Needs you is a screen, not a feed · N1, nav, tab title · a "New" mark (text) on an item that arrived while you were elsewhere, cleared on open; "Recently cleared" (last 5, from Activity); `document.title` prefixed "(1) "; no push, no sound (M) · both (MM M-13, SN M-15)
- [x] MP-17 · No record of what changed · Settings > Activity (new T5) · session event log, newest first, capped at 200, times from the mock clock, "simulated" where simulated; empty = `empty-ledger` "Quiet so far."; says "This session only." and is never stored (L) · SN M-16
- [x] MP-18 · Disconnect has no real undo; the note vanishes on navigation · D1 note and toast · visible "Undo" for 30 seconds of mock time restores the service exactly (facts, selection, kept-out, frame) with Dot carrying the parcel back; after 30s the snapshot is dropped and "Reconnect" (full Connect) remains; Revoke has none (M) · both (MM M-08, SN M-17; window set to 30s)
- [x] MP-19 · About is one block mixing replay buttons and mock controls · Settings · split into **Help** (words, reference, who can act, replay, how one fact travels, keyboard, doors), **About** (MOCKUP, synthetic, UTC, mock-clock line, UNKNOWNs as a short list, links to the Field Guide map, this spec and the Connect contract), and **For reviewers** (collapsed, own heading, failure and edge controls only) (M) · both (MM M-25, SN M-18)
- [x] MP-20 · The Field Guide skeleton (Home, Explore, Needs You, Guide) is invisible to the person · Help · four one-line entries mapping each door to its Worlds destination (Explore = Connect, Guide = Memory) and a link to the Field Guide; nav labels stay Worlds words (S) · Field Guide (`world-tree-MAP.md`, `world-tree-GLOSSARY.md`); neither audit Built as one Help entry listing the four doors.
- [x] MP-21 · Replaying the welcome overwrites live services · Help > Replay · a tour in a copy: beats run on a throwaway store, labelled "Replay. Nothing changes."; never mutates real instances (S) · SN M-19
- [x] MP-22 · No way back to a clean first run, and the simulated change is one-way · For reviewers · "Start over" with confirm ("Clears this browser's mock. Nothing else."); "Home reports it unlocked again" (S) · both (MM M-14, SN M-20)
- [x] MP-23 · Settings renders every section at once · Settings · only the routed section renders; the section list is real links with `aria-current="page"`; phone is a list of sections, each a pushed screen with Back (M) · both (MM M-17, SN M-8)
- [x] MP-24 · Settings sections have no loading or error state · T1-T8 · static "Fetching settings…" on first entry per session; error "Couldn't save that. Nothing changed. Try again." reachable by "Make the next save fail" (M) · both (MM M-18, SN M-7)
- [x] MP-25 · Phone pushed service screen has no Back in the top bar · header · header button becomes Back to `#/home`, focus returns to the slip (S) · MM M-15
- [x] MP-26 · Phone welcome beats have no live or simulate controls · W1-W3 · same status row as other top-level screens (S) · MM M-16
- [x] MP-27 · "How one fact travels" can land on nothing · Help, note · selects Media Shelf first (or shows its example statically when it isn't connected), then shows the note on its first fact (S) · both (MM M-19, SN M-12)
- [x] MP-28 · Offline can't be tested on demand · For reviewers · "Go offline (mock)" toggles the same state the browser events use (S) · MM M-20
- [x] MP-29 · Owner links die on middle-click and open a modal · every `app://` link · render as `#/owner/{app}` (a real route); open a non-modal note anchored to the link, Escape returns focus to it; the handoff dialog stays open under it (S) · SN M-25, B-28
- [x] MP-30 · App frame lifecycle is a timer · S2 · add `cancelled`; load only when the App pane is visible; hard 8s timeout "Too slow."; "Reload" on loaded; reviewer select "Make the next frame fail: refused / slow / never"; by default the first two tries fail, then it loads (S) · both (MM B-12, SN M-26, B-25, R-30)
- [x] MP-31 · Escape in Connect drops a typed reference · C2-C5 · if anything was typed or ticked, the first Escape says "Nothing saved yet. Escape again to leave."; Cancel leaves at once (S) · SN M-27, B-9
- [x] MP-32 · Times are UTC-only · Settings > Live feed · "Times": UTC (mock default) or This device (S) · SN M-28
- [x] MP-33 · `disabled` is in the fixture vocabulary but not the spec · §4.9 · say Worlds never shows it (no fixture service uses it); the chip renders an unknown state as its own word and never throws (S) · SN M-9
- [x] MP-34 · Welcome beats: duplicate Back, no step cue · W2, W3 · one Back, quiet "1 of 3", Skip on every beat (S) · SN M-10
- [x] MP-35 · Nothing says what changed while the tab was hidden · status area · on return after 60s: "Away 4m. 1 thing changed." linking to Activity; never a modal (M) · SN M-22
- [x] MP-36 · The Add-service pill shows where it means nothing · phone · hide on Needs you and Settings; on Memory only when empty (S) · MM M-24
- [x] MP-37 · Every list needs its own empty state · table in §4.0 · Memory service with no facts, Discover with no candidates, References, Activity, Needs you (M) · SN M-24 (MM M-07)
- [x] MP-38 · The contract's `board` is never shown · C6 · recorded as UNKNOWN Q10 in §12; Worlds has one board, no control (S) · MM M-21

### Reactive

- [x] RX-01 · P0 · State is one module object re-rendered wholesale; nothing persists · all views · small store with get/set/subscribe and selectors; slice rendering so a tick repaints ages only and a change repaints the places it appears; append-only event log; the user-owned part saved to `localStorage` under `worlds-mock-v1` (L) · both (SN R-1, R-2, B-22; MM M-14, B-27) Built: the store (get/set/subscribe, event log, saved user-owned part) and slice rendering on it — the tick repaints age text and the freshness line only, and a state change emits one store topic that repaints just the slices subscribed to it (slips and selected card, finder counts, Memory rows and counts, Needs you list and badge, Settings rows, the service detail, the note and the chrome), keeping focus, caret and scroll per slice. The page test asserts the view's own nodes survive both a tick and a change.
- [x] RX-02 · P0 · Mock clock drifts and stops in hidden tabs, and freezes during the welcome · LiveTick · `now = T0 + (performance.now() - t0) - pausedTotal`; on `visibilitychange` apply every scripted event that passed, in order, then render once; the welcome doesn't freeze the clock (S) · both (MM R-01, B-21; SN R-3)
- [x] RX-03 · P0 · Relative time has no "now" and no day unit ("checked 100h ago") · FreshnessBadge · under 5s "just now", then s, m, h, d; one unit; absolute time in `title` and hidden text (S) · SN R-4
- [x] RX-04 · P0 · A scripted Stale or Unknown doesn't settle the receipt or nod · ChangeRipple · the rule returns `{service, fact, to}`; the tick handler sets the same settle, nod and "Updated now" as `#simulate-change`, and a re-render at expiry clears them (S) · SN R-5
- [x] RX-05 · Unknown-on-silence has no general rule · FreshnessBadge · a Live fact with no successful check for 3× its re-check interval (90s) is Stale, for 5× (150s) Unknown, for every live fact; the scripted events become this rule at a short fuse; documented in §9 and Q6 (M) · SN R-6
- [x] RX-06 · "Live · checked 24s ago" can contradict the data, and the freshest check hides an old one · status line, toggle · if the freshest check is older than 2× the interval it reads "Live · none current"; the status line adds "oldest 8h" when the oldest is over an hour older than the freshest (S) · both (MM R-17, SN R-7, R-29)
- [x] RX-07 · P0 · Toast is one overwritten slot, and polite regions are duplicated inside re-rendered markup · Toast + live region · one polite `role="status"` created once and never re-rendered, one assertive `role="alert"` for a failed test or publish only; messages within 500ms batch with " · "; at most one polite message per 2s; field messages tie by `aria-describedby`; §8.3 corrected to say one polite and one assertive (S) · both (MM R-13, SN R-9)
- [x] RX-08 · Toast lifetime, dismiss, action slot, phone placement · Toast · lasts `max(4s, 60ms × characters)`, pauses on hover or focus, "Dismiss" when it carries an action, sits above the add pill on phone, one at a time with a queue (S) · both (MM R-13, M-08; SN R-10)
- [x] RX-09 · "Updated now", the nod and the settle are render-time clocks · ChangeRipple · store flags with a timeout; settle keyed by a change sequence so a cadence tick inside the window doesn't replay the stagger; "Updated now" fades at `--wv-dur-state` (S) · both (MM R-20, R-21, P-06; SN R-11)
- [x] RX-10 · P0 · Optimistic actions can't fail and can't roll back · OptimisticAction · one helper (apply, work, undo); wire Publish, Disconnect (with Undo), Revoke, Replace, Rename, Change what's shown, Settings saves; each failure reachable from For reviewers (M) · both (MM R-07, R-08; SN R-12) Replace saves only after its test passes, so it needs no roll back.
- [x] RX-11 · Settle misses the slip chip, fact row and Memory rows of the changed fact · ChangeRipple · settle every node carrying `data-fact` for that id (S) · SN R-13
- [x] RX-12 · Loading exists for three things only · Skeleton/loading · static placeholder on first entry per session (300ms) for Settings, Memory, Discover; Memory's is three still sunken rows with "Fetching facts…"; "Make the next screen fail to load" makes X1 reachable; no spinner, no shimmer (M) · both (MM R-10, R-11; SN R-14)
- [x] RX-13 · No sense of how long a wait is · Test, Preview, Frame · words only: after 3s "Still reading. 4s."; "Stalled?" link at 6s, not 0; real timeout at 10s with Try again; Preview names its stage ("Reading." then "Shaping facts.") and "Reading 2 of 3 facts" when known (S) · both (MM R-12, SN R-15)
- [x] RX-14 · P0 · Offline doesn't do what the spec says · X1, LiveTick · states keep their own words (Worlds doesn't invent Stale); each Live fact swaps "Live" for "Offline · last checked 3m ago" and ages freeze; the pause button reads "Paused · offline" (`aria-disabled`) and the person's own live/pause choice is remembered and restored; on return one re-check of every Live fact, strip "Back online. Checking." until it resolves, then "Checked just now." (M) · both (MM R-14, R-15; SN R-16, R-17, R-23); §4.14 amended
- [x] RX-15 · Nothing retries · LiveTick · a missed re-check retries at 2s and 4s, then goes Stale by the rule; an Unavailable service's read is re-attempted at 15s, 30s, 60s, 120s, then every 5 min, ±20% jitter, with "Next try in 30s."; attempts never change a value or `checkedAt`; "Check now" resets the ladder; paused while paused or offline; owner retries stay links (M) · both (MM R-16, SN R-18)
- [x] RX-16 · Resume after a long pause jumps to "stale" · LiveTick · after a pause over 60s, resume re-checks every Live fact once (S) · SN R-19
- [x] RX-17 · Counters and badges · Counter/badge · badge caps at "9+"; status line pluralises ("2 need you"); chips carry counts in text; the count is the number of decisions waiting; `document.title` prefix (S) · SN R-20, R-32 (decision)
- [x] RX-18 · State-word cross-fade is spec-only · FreshnessBadge, chip · the chip keeps its node and swaps text and glyph with a 150ms opacity transition (S) · SN R-21 Built as a 150ms opacity fade on the re-drawn chip (the node itself is re-created).
- [x] RX-19 · Reduced-motion leaks · Dot, stamp, parcel, buttons · no nod pose swap, no 60ms lane flash, `.btn:active` transform zeroed, one `motionOK()` that reads the OS setting and "Reduce always" (S) · both (MM R-18, P-15; SN R-22)
- [x] RX-20 · The live toggle's name churns with the age and is announced twice · `#live-toggle` · id and checker keep working; button text is "Live" or "Paused" with `aria-pressed`; the age sits in an adjacent text node, tabular figures, fixed width (S) · SN R-25 (decision)
- [x] RX-21 · `#simulate-change` is live when it can't act, and its label goes stale · top bar · `aria-disabled` with visible reason "Connect Front Door first"; after the press it says "Already reported locked." and its label updates; reviewers get the reverse control (S) · both (MM B-15, SN R-26)
- [x] RX-22 · Two changes in one second lose one message · Toast · lists batch ("Media Shelf and Notes Sync are now Stale.") (S) · SN R-27
- [x] RX-23 · Cadence change gives no feedback · Settings > Live feed · the anchor resets; one debounced announcement (S) · SN R-24, B-4
- [x] RX-24 · "One change, every view" can be visited but not seen · note after `#simulate-change` · names the places that moved: "Counter, Needs you and Agent facts all show it now." (S) · MM R-06
- [x] RX-25 · Nothing can become Needs you except the one scripted change · For reviewers · "Make Studio Printer need you (mock)" so the New mark and the badge have something to arrive (S) · MM R-22
- [x] RX-26 · Pending states are fixed timers · all mock work · latency ±25%; "Simulate slow" multiplies by 8 so stalls are testable (S) · SN R-31

### Robustness

- [x] RB-01 · P0 · "Skip to Worlds" lands on "Couldn't load this." · skip link · handle the click: focus `main`, don't change the hash (S) · MM B-01
- [x] RB-02 · P0 · A pasted secret sits in the Replace field until Save · Settings > References · validate on blur and on paste; clear on a secret shape; never put the value into the store, log or DOM text (S) · both (MM B-07, SN B-1)
- [x] RB-03 · A malformed but harmless reference is called a secret, and 50+ characters is refused as one · C2, Replace · two refusals: "Not a reference. Use ref://name." keeps the text; the secret refusal clears and is for secret shapes only (token prefixes, long hex or base64); live "n/49" (S) · both (MM B-06, SN B-2)
- [x] RB-04 · Double activation runs things twice · confirm and Next buttons · one `once(key)` guard, `aria-disabled` at once, focus stays; ignore `e.repeat` on Disconnect, Revoke, Publish (S) · both (MM B-13, SN B-3)
- [x] RB-05 · The last-item rule behaves two ways · C5 vs welcome · both: the last tick is `aria-disabled` with "Keep at least one." (S) · SN B-6
- [x] RB-06 · Abandoned work still announces · Connect, Back/Escape/hashchange · cancel timers on route leave; no announcement for work the person left (S) · SN B-7, B-10
- [x] RB-07 · Failed-test cause is a literal · C3 · use the fixture `lastError`, else a short classed list ("Provider timed out.", "Reference refused.", "Unreachable."); never a provider's free text (S) · SN B-8
- [x] RB-08 · Browser Back leaves a dialog up over another screen · dialogs, sheets · close on `hashchange`; on phone a sheet pushes a history entry so Back closes it (M) · SN B-11
- [x] RB-09 · P0 · A re-render wipes typed text, focus and the open select · all views · until slices land: defer a repaint while a text field or select has focus; every button carries a stable `data-fk`; keep the Replace value, caret and scroll (M) · both (MM B-02; SN B-12)
- [x] RB-10 · P0 · Focus drops to `<body>` after dismissals · notes, Replace Save, frame buttons · restore by `data-fk`, else the nearest preceding heading (S) · both (MM B-02, SN B-13)
- [x] RB-11 · Phone tabs claim to be a tablist and aren't · S1 phone · three `aria-pressed` buttons, inactive panes `hidden` (S) · SN B-15
- [x] RB-12 · Very long names break the bar and the slip · top bar, slips, Settings · cap 40; the `#disconnect` label stays on one line to 20ch with an ellipsis, full name in `aria-label` and `title` (the one documented exception to "never truncate"); the slip header wraps with the chip under the name (M) · SN B-16 (MM B-18)
- [x] RB-13 · P0 · 20+ services isn't designed · Home, Memory, Settings · the slips column scrolls on its own with a sticky detail; selecting scrolls the detail into view and a one-line "Selected" bar sticks; groups by state over 12 as `<details>` with counts; Memory services collapse (open for 6 or fewer); "Make 24 services" for reviewers (L) · both (MM M-26, B-17; SN B-17) Built: the slips column scrolls on its own and sticks; the detail pane flows with the page.
- [x] RB-14 · Zero facts leaves a heading with nothing · Memory, receipt · "No facts. {emptyReason}" under the heading; owner link in the receipt (S) · SN B-18
- [x] RB-15 · Forty facts push the receipt off screen · fact list · scrolls in a 12-row box with "Show all 40"; the selected fact's receipt scrolls into view (S) · SN B-19
- [x] RB-16 · "1 jobs", "1 minutes" · fact value · plural by unit table (S) · SN B-20
- [x] RB-17 · P0 · "2:23 PM" has no zone · every absolute time · print "2:23 PM UTC" (or the device zone's abbreviation, MP-32); older than today shows the date (S) · both (MM B-20, SN B-21)
- [x] RB-18 · P0 · Reload forgets everything · store · persist theme, motion, cadence, times, welcomeDone, journeySeen, instances (name, reference, scope, kept-out, connectedAt), selection, filter, sort; never persist a typed field, a refused value, the clock, scripted state, the Activity log or the undo snapshot; bad or blocked storage runs in memory silently (M) · both (MM M-14, B-27; SN B-22, B-27)
- [x] RB-19 · The mock clock isn't explained · About, status line · "Mock clock starts at 2:24 PM UTC on Oct 13. Real time isn't used."; `title` "mock time" (S) · SN B-23 Built: About line, and the status line's `title`.
- [x] RB-20 · Age boundaries untested · FreshnessBadge · unit test at 0, 4, 5, 59, 60, 3599, 3600, 86399, 86400 seconds (S) · SN B-24
- [x] RB-21 · A loaded frame can die, and the real iframe needs a build note · S2 · hard timeout (MP-30); build note: the real frame carries `sandbox` without `allow-same-origin`, and `referrerpolicy="no-referrer"` (S) · SN B-25
- [x] RB-22 · Actions that would call out run while offline · Test, Re-test, Publish, Replace · `aria-disabled` with "Offline."; Disconnect stays allowed ("Offline. Removed from Worlds.") (S) · SN B-26
- [x] RB-23 · Slip names, ticking ages and selection are read badly · slips · `aria-label` per §8.3 with the age written once at render; the ticking span is `aria-hidden`; "Selected Front Door." announced on desktop; test with NVDA, VoiceOver (macOS, iOS), TalkBack (M) · both (MM B-24, SN B-29) Built: the slip's accessible name is written once at render (name, state word, age, and "selected" when it is), the ticking age inside the slip stays `aria-hidden`, and only state-word changes, selection, connect, disconnect, undo and errors reach the one polite region. The page test checks the labels, that "selected" is present exactly when the slip is pressed, that there is one polite region, and that ticks never announce. Screen-reader pass still owed by the owner (below, RB-24).
- [x] RB-24 · Contrast not measured on the build · four themes · measure the needs-you badge pair, Dot and art on each surface, the toast border, the `aria-disabled` look; run axe; add `forced-colors` rules (borders and outlines survive, shadows don't, so the add pill gets a real border) (S) · both (MM B-23, SN B-30) Built: axe across all four themes (dark, light, high-contrast, low-stimulation) on welcome, Home, Connect and Needs you reports no violations, and the `forced-colors` block maps text, borders, focus rings, badges and status chips to CanvasText, Canvas, LinkText, Highlight, HighlightText, GrayText, ButtonText and ButtonFace, keeps the state words visible, and lets only the art opt out (`forced-color-adjust: none` on images). The page test asserts that one block exists, that it names every system colour, and that nothing but images sets `forced-color-adjust`.
  Human screen-reader and contrast check: NOT RUN, owner check (Rylee).
- [x] RB-25 · 200% text hides content under the sticky bar · top bar, tab bar, add pill · measure the bar with a `ResizeObserver` into `--wv-top-h`; no fixed heights; drop `min-width` on body; scroll padding follows (S) · both (MM B-03, B-25; SN B-31, B-33)
- [x] RB-26 · 320px isn't designed · Connect bar, header, fact rows, dialog buttons · the Connect bar wraps to two rows under 24rem; the header Settings button becomes the icon with its full name; fact rows stack label and age over value and chip; dialog buttons stack (S) · both (MM B-26, P-05, P-07; SN B-32)
- [x] RB-27 · Titles, landmarks and skip target · document · `document.title` per route via `textContent`; one `nav` exposed per width; a second skip link "Skip to navigation" on phone (S) · SN B-34, B-35
- [x] RB-28 · Names are a new markup surface (rename, search, title) · everywhere · a test string table (markup, quotes, RTL override, zero-width, emoji joiners) viewed on every screen (S) · SN B-36
- [x] RB-29 · Keyboard and focus traps unchecked on the build · all screens · Tab and Shift+Tab pass, 4 themes × 3 widths; keyboard list in Help; native `<dialog>` stays (S) · both (MM B-04, SN B-14) Tab and Shift+Tab run at 1440, 768 and 390 in all four themes on Home, Connect and Memory; dialog trap and Escape checked.
- [x] RB-30 · Images start with an empty `src` · art helpers · transparent data URI until the art resolves (S) · MM P-03
- [x] RB-31 · Acceptance isn't automated · one HTML page test, no network · asserts: no length literal in padding, margin or gap outside `:root`; no inline style with a length; age boundaries; a refused secret never reaches DOM or storage; one polite and one assertive region; every `data-act` has a stable `data-fk`; the §10 proof path end to end including offline, reload and 24 services (M) · both (SN appendix; MM exit check) Built as `index.html?test` (a page test, 53 checks, no network); the reload step is a save and load round trip.

### Polish

- [x] PL-01 · Off-ladder spacing and literals against the spec's own rule · stylesheet · snap to `--space-*`; add a few local handles (`--wv-pad-tight`, `--wv-measure`, `--wv-panel-w`, `--wv-hero-w`, `--wv-scene-w`, `--wv-toast-w`, `--wv-station-min`, `--wv-icon-sm`, `--wv-icon-lg`); inline styles become classes; a script check in the page test (M) · both (MM P-01, SN P-1)
- [x] PL-02 · Section headings shrunk by inline `--type-h1` · Memory, Needs you, Settings, Discover · one ladder: page `--wv-display-page`; section `--wv-display-section`; card title in a list `--type-h1` (`.h-card`); slip name `--type-lead` (S) · both (MM P-02, SN P-2)
- [x] PL-03 · Button hierarchy · Connect, top bar, Settings rows · one mint button per view (Run safe test goes secondary once it has passed); desktop Disconnect is text-weight danger with its border on hover and focus, word unchanged; Settings row order Rename · Test again · Replace · Remove (S) · SN P-6, P-18
- [x] PL-04 · Ages jitter · live label, `[data-ak]` · tabular figures; a fixed minimum width on the toggle (S) · SN P-7, P-8
- [x] PL-05 · Chip glyph weight and baseline differ from nav glyphs · chips, rail · match optical stroke per size; centre the text baseline (S) · SN P-4
- [x] PL-06 · "(simulated)" after every chip is a wall of text · slip, row, receipt, Memory · one visible "simulated" per card (the receipt); elsewhere a small "sim" pill with the full word in `title` and hidden text (S) · SN P-5
- [x] PL-07 · Slip peek and fact row emphasise opposite things · slip, row · the value is the lead (`--type-lead`), the label small and soft; one "last known" construction in both (S) · both (MM P-04, SN P-9)
- [x] PL-08 · The receipt isn't visibly the hero · S1 · more padding, 2px frame, value line in `--type-h1`; fact rows lighter; slips → receipt → facts reads in that order; still depth by surface (M) · SN P-14
- [x] PL-09 · Memory's fact cards are heavy · Memory · collapsed to one row (label, value, chip, age) with a disclosure; Unknown rows start open (M) · SN P-17
- [x] PL-10 · Empty wells too tall at narrow desktop · empty states · art capped at 40% of the well; text keeps 28ch (S) · SN P-15
- [x] PL-11 · The count word in the status line is as light as the rest · status line · bold the count word only (S) · SN P-16
- [x] PL-12 · The stamp reads as a flash, and clips when tilted · stamp · `--wv-dur-stamp` 280ms (scale 1.35 to 1, then a 40ms settle); padding for the rotated corner; checked at 320 (S) · both (MM P-13, SN P-11, P-25); decision
- [x] PL-13 · Dialog and phone sheet share one entrance · dialog, sheet · the sheet rises from the bottom edge, the dialog fades and lifts 1rem; both instant under reduced motion (S) · SN P-12
- [x] PL-14 · Connect steps swap instantly though §8.1 says fade · Connect · 150ms opacity on step change (S) · SN P-13
- [x] PL-15 · Dot placements drift from the spec · H0, Connect, Needs you, load error · H0 gets `dot-asleep` in the well; Connect's header gets the freshness line with Dot at rest; Needs you's header drops Dot while items exist; load error uses `dot-tucked` in the full-page well; curious beside Stale and goodbye after disconnect stay (decisions) (S) · both (MM P-08, P-09, P-10; SN P-19, P-20)
- [x] PL-16 · Dot is soft and a half-step big · header, wells · `.lg` capped at 7rem (a 448px re-render isn't in this round); header Dot 3.25rem phone, 3.75rem tablet (S) · SN P-21, P-22
- [x] PL-17 · Service icons shift the name when missing and differ in height · slip, header, Discover · fixed square box per size, only `--wv-icon-sm` and `--wv-icon-lg`; lookup by `templateId`; `icon-generic` fallback; `icon-local-weather` placed in Providers (S) · both (MM P-11, P-12; SN P-24)
- [x] PL-18 · The new art isn't placed · see §4.0 · `dot-peek` (no matches), `dot-tucked` (full-page offline and load-error wells), `dot-settled` ("{Name} is here."), `scene-quiet` (Needs you empty, no Dot), `empty-ledger` (Activity empty, nothing held), `icon-generic` (S) · both (MM art 1, 3, 4, 5; SN art 1, 2, 3, 5, 6)
- [x] PL-19 · The tab bar's "you are here" is a 1px line · phone tab bar · stronger indicator (the sunken surface plus the existing `aria-current` word) (S) · MM P-16
- [x] PL-20 · Rail badge overlaps wrapped labels · tablet rail · fixed corner at the icon; labels fit at 200% (S) · SN P-10
- [x] PL-21 · Parcel travel is a guess at the lane width · parcel · start at `translateX(-100%)` of Dot's own width so travel is proportional (S) · MM P-14
- [x] PL-22 · Copy for the new pieces · §7 · strings in terse warmth; no exclamation marks (S) · SN P-28
- [x] PL-23 · Small warmth that needs no new art · Dot · the parcel carried back on Undo (mirrored `dot-parcel`); `dot-welcome` in Help's header; one nod when the counter turns calm after a real owner change (S) · SN P-23

### Not doing, and why

- Keeping history after disconnect, and a "Recently disconnected" list with a 30-minute undo (SN M-17): decision. Undo is 30 seconds and the history question stays open. Activity is session-only and never stored.
- Removing the curious Dot beside Stale, or Dot's goodbye (MM P-08, SN P-19): decision, both stay.
- Relabelling Live facts as Stale while offline (SN R-16): Stale means a missed re-check; offline gets its own qualifier (RX-14). §4.14 amended.
- Pausing in-flight tests, publishes and frame loads when the feed is paused (MM R-19): §9 says actions still work while paused.
- Quiet auto-retry of Needs-you services (SN R-18 as worded): they wait on a person; only Unavailable services are re-attempted.
- Push or browser notifications and sounds (SN M-15): Worlds shows, never pesters. Stated in §4.7.
- Single-key shortcuts such as `/` for search (MM's list): §8.2.
- Any control, flag or "Link ready" state that makes approvals look connected (MM's list): Sol condition 1.
- Painted sticker icons in the nav (MM P-12): line glyphs stay stand-ins.
- Art outside the list given for this round: `dot-shrug`, `hero-front-door`, `scene-frame-refused`, `scene-no-match`, `empty-tray`, and a 448px re-render of the Dot poses (SN, MM). `dot-peek`, `scene-quiet`, `empty-ledger`, `icon-generic` and size capping cover the same needs.
- A "Board" control in C6 (MM M-21): one board only; recorded as UNKNOWN Q10.
- Counting services rather than decisions in the Needs you badge (SN R-32 "leave"): decision, it counts decisions.

## Reactive components

The prototype builds these once and uses them everywhere; no screen draws its own version. Each has props, states, transitions, a reduced-motion form and an announcement rule. Shared rules: motion confirms a change that has already happened (§1 item 13), uses `--wv-ease`, and under reduced motion (OS setting or "Reduce always", one `motionOK()`) becomes opacity-only or instant while data never stops. Words carry every state; colour, glyph and Dot are supplemental. Routine ticks are never announced.

### LiveFactRow

One fact, drawn the same everywhere.
- **Props:** `factId`, `label`, `value`, `state` (own state, never merged with the service's), `checkedAt`, `changedAt`, `source`, `agentCan`, `humanCan`, `reason`, `simulated`, `variant` (`peek` on a slip, `row` in S1, `card` in Memory, `agent` in the Agent view tab, `preview` in C4/C5).
- **States:** live, stale, unavailable, unknown, not configured; offline-qualified (RX-14); selected; settling; kept out (named in the kept-out line, never drawn); permission none (named, focusable, `aria-disabled`, reason visible).
- **Transitions:** the value never changes except by an owner event (§9). A state change swaps word and glyph on the same node with a 150ms (120ms phone) cross-fade; settling is the 60ms tick across the nodes carrying this `data-fact` (see ChangeRipple).
- **Reduced motion:** instant swap, all ticked at once.
- **Announcement:** silent itself. A state change goes to the Toast queue once, batched ("Media Shelf is now Stale."). The accessible name is built once at render and doesn't include the ticking age.
- **Used by:** Home (slip peek), S1 (fact list, receipt), Memory, Agent view tab, Connect C4 and C5 (static).

### FreshnessBadge

The word and the age for a fact, service or feed. Ladder: **live → ageing → stale → unknown**.
- **Props:** `state`, `checkedAt`, `interval` (re-check, 30s), `paused`, `offline`, `scripted`.
- **States:** **live** (age up to 45s): "Live" with "checked 24s ago". **Ageing** (45s to 90s, the re-check is late): still "Live", with "checked 52s ago · re-checking" in soft text, no new word. **Stale** (90s, 3× the interval, or the fixture says so): "Stale", last value as "last known", "No change seen since {time} UTC." **Unknown** (150s, 5×): "Unknown", "No current reading. Not guessing.", last value only as "last known". Offline and paused don't advance the ladder: **offline** shows "Offline · last checked 3m ago" in place of Live; **paused** shows "frozen at 24s". A fact never checked is Unknown. Fixture states (Needs you, Unavailable, Stale, Unknown, Not configured) never re-check and keep their words; their ages grow.
- **Age text:** under 5s "just now", then `Ns`, `Nm`, `Nh`, `Nd`; one unit; tabular figures; absolute time in `title` and hidden text.
- **Transitions:** word and glyph cross-fade 150ms (instant under reduced motion); the age number changes in place and nothing else moves.
- **Announcement:** into Stale or Unknown, once, batched. Ageing and age ticks are silent.
- **Used by:** slips, fact rows, receipt Source station, Memory, status line (freshest, and "oldest 8h" when over an hour apart), top bar, Settings rows.

### ServiceCard

The unit of the counter, in four variants: **slip** (Home), **card** (Needs you), **row** (Settings, Connected services), **candidate** (Discover).
- **Props:** `instanceId`, `displayName`, `kind`, `ownerApp`, `state`, `factState` (when it differs), `reason`, `peek`, `checkedAt`, `selected`, `isNew`, `variant`.
- **States:** default, hover (lifts about 2px, border turns mint), selected (word "Selected", check shape, mint border), focus (`--focus-ring`), healthy, needs you, stale, unavailable, unknown, not configured (Providers rows only), **pending** (optimistic add, behind the Connected card), **removing** (optimistic remove), **New** (text mark on Needs you), filtered out (not in the DOM), many-facts line ("1 stale.").
- **Transitions:** lift and border 150ms; chip cross-fade; a new slip appears in the same frame the person acts, then settles with the parcel and stamp (RM: in place).
- **Reduced motion:** no lift; border and word still change.
- **Announcement:** `aria-label` "Front Door, Needs you, checked 24s ago, selected", with the reason via `aria-describedby`; selecting on desktop says "Selected Front Door."; a new Needs you item announces once.
- **Used by:** Home, Needs you, Settings > Connected services, Discover, Memory headings (name, chip, freshness, owner link).

### DotMood

Dot's pose is bound to app state, never to good or bad. One Dot per view at most; Dot is `aria-hidden` unless a sentence names Dot; Dot never appears in a toast, strip, dialog or sheet.
- **Props:** `mood`, `size` (`rest` or `lg`), `mirrored` (parcel back).

| Mood | Art | Bound to | Notes |
|---|---|---|---|
| rest | `dot` | header beside the freshness line on Home, Connect, Memory, Settings; test, preview and frame loading | still |
| asleep | `dot-asleep` | W1; empty counter H0; Memory empty; empty lists that carry a well | "z"; falls asleep 200ms when the counter becomes empty |
| welcome | `dot-welcome` | W2 hero beat; Help header | |
| nod | `dot-nod` | a state word changed, beside "Updated now" | 200ms, once, 3s; never on a plain tick |
| parcel | `dot-parcel` | Publish; welcome connections; **mirrored** on Undo | 400ms desktop, 300ms phone |
| settled | `dot-settled` | after the stamp, beside "{Name} is here." | static |
| goodbye | `dot-goodbye` | the note after a disconnect (outside the dialog) | static |
| curious | `dot-curious` | beside the chip in a Stale service's header | static; the words say it's stale, not the pose |
| peek | `dot-peek` | search or filter with no matches | static |
| tucked | `dot-tucked` | full-page "Couldn't load this" and full-page offline wells only | never in the strip |

- **Quiet list (no Dot):** Needs you items, N2 handoff, D1, R1, reference refused, secret refused, failed test, failed publish, save failed, the offline strip, Reviewer controls. Needs you's empty state uses `scene-quiet` with no Dot.
- **Transitions / reduced motion:** the nod, parcel and fall-asleep move; under reduced motion no pose swap for the nod, the parcel appears at the counter, asleep is a pose change only.
- **Announcement:** none.
- **Used by:** every screen per §4.0.

### Counter / badge

A number in text.
- **Props:** `count`, `noun`, `cap` (9), `scope` (nav, status line, filter chip, tab title).
- **States:** 0 (no badge; the status line says "Nothing needs you."), n, "9+". The count is decisions waiting, not services. "2 need you" pluralises.
- **Transitions:** the number swaps with a 150ms fade; no bounce.
- **Reduced motion:** instant.
- **Announcement:** the nav badge reads "Needs you, 1". Count changes are carried by the change message, not announced on their own. `document.title` gets "(1) " when the count is above 0.
- **Used by:** rail and tab bar, status line, filter chips, Needs you heading, tab title.

### ChangeRipple

One fact updating many views.
- **Props:** `factId`, `seq` (change sequence), `origin` (owner, rule, or feed), `from`, `to`.
- **Behaviour:** one store change; every node carrying that `data-fact` settles: receipt stations **Source → Worlds → Agent / Human**, 60ms apart (the third station keeps its §4.5 label, Q7), plus the slip chip, the fact row and the Memory row. "Updated now" fades in for 3s with Dot's nod. A note names where it moved ("Counter, Needs you and Agent facts all show it now."). The origin is said plainly ("The Home app reported the back door locked. Worlds locked nothing.", or "(simulated)" for the rule). The class is keyed by `seq`, so a cadence tick or re-render inside the window never replays it.
- **States:** idle, rippling, settled.
- **Reduced motion:** all stations tick at once; no nod; "Updated now" still shows 3s.
- **Announcement:** one batched polite message ("Updated everywhere. Home reported the back door locked. Worlds locked nothing.").
- **Used by:** `#simulate-change` and its reverse; the scripted Stale and Unknown; Check now; Replace reference passing; Home, S1, Needs you, Memory.

### LiveTick

The feed clock.
- **Props:** `cadence` (5, 10, 30s), `live` (the person's choice), `offline`, `visible`.
- **Clock:** `now = T0 + (performance.now() - t0) - pausedTotal`, starting at the fixture's `generatedAt`; it runs from page load, including through the welcome. Ticks only schedule repaints of ages. On return to a hidden tab it catches up, applies every scripted event that passed in order, renders once, and says "Away 4m. 1 thing changed." after 60s.
- **States:** running; **paused** (the toggle: freezes clock, ticks, re-checks and scripted timers; actions and `#simulate-change` still work; reads "Paused · frozen at 24s"); **offline** (paused by the browser: "Paused · offline", `aria-disabled`; the person's own choice is remembered and restored); **catching up**; **slow** (reviewer: latency ×8).
- **Re-check and backoff:** a Live fact re-checks every 30s. A missed re-check retries at 2s and 4s, then goes Stale by the 3×/5× rule. An Unavailable service's read is re-attempted at 15s, 30s, 60s, 120s, then every 5 minutes, ±20% jitter, "Next try in 30s."; an attempt never changes a value or `checkedAt`. Needs you services aren't retried (they wait on a person). "Check now" resets the ladder. Backoff doesn't run while paused or offline. After a pause over 60s, resume re-checks every Live fact once.
- **Toggle:** `#live-toggle` keeps its id and `aria-pressed`; its text is "Live" or "Paused"; the age ("checked 24s ago", or "none current") is a neighbouring text node. `#settings-live` always agrees.
- **Reduced motion:** nothing moves on a tick except the age number, so no change.
- **Announcement:** "Paused. Freshness frozen." / "Live feed on." once each; offline and back online once each; ticks silent.
- **Used by:** top bar and status row (every screen), Settings > Live feed, every FreshnessBadge.

### Toast + live region

- **Props:** `text`, `kind` (info, done, failed), `action` (label and handler, optional), `loud` (assertive).
- **Regions:** one polite `role="status"` created once and never re-rendered, and one assertive `role="alert"` used only for a failed test or failed publish (and never also written to the polite one). Messages inside 500ms batch with " · "; at most one polite message every 2s; the queue sits behind the visible toast. Field messages (reference check, test result) are plain text tied by `aria-describedby`, and their announcement goes through the same region.
- **Toast:** lasts `max(4s, 60ms × characters)`, longer while paused; pauses while hovered or holding focus; "Dismiss" when it carries an action (Undo, Reconnect); on phone it sits above the add pill; `--surface-raised`, `--status-done` border (a real border, so it survives forced colours).
- **States:** hidden, visible, paused (hover or focus), queued.
- **Transitions:** fade and rise 200ms (`--wv-dur-sheet`); instant under reduced motion.
- **Announcement:** this is the announcement path for everything else.
- **Used by:** every screen.

### OptimisticAction

Do it now, settle it, or roll it back.
- **Props:** `apply`, `work` (a promise; mock latency ±25%), `undo`, `failText`, `window` (Undo window, 30s of mock time, only for Disconnect).
- **States:** **pending** (the result is in the same frame; the control is `aria-disabled`, focus stays) → **settled** (parcel, stamp or removal message names what changed) or **rolled back** (`undo()` runs, the screen returns to what it was, one assertive or polite failure message with the cause, focus on the control that was pressed, an Activity entry). Disconnect adds **undoable** for 30 seconds: a visible "Undo · 24s" (text, counts down on the mock clock) restores the service exactly with the parcel carried back; at 0 the snapshot is dropped and only "Reconnect" (full Connect) remains. Revoke has no undo.
- **Used for:** Publish (fails by control: slip leaves after 900ms, "Didn't publish. Nothing was added. Try again."), Disconnect, Revoke ("Couldn't remove that. Nothing was changed."), Replace reference, Rename, Change what's shown, Settings saves ("Couldn't save that. Nothing changed. Try again.").
- **Reduced motion:** same sequence, no parcel travel or stamp scale.
- **Announcement:** success once, batched; failure once.
- **Used by:** Connect, Home, Settings, D1, R1.

### Skeleton / loading

Static, never animated.
- **Props:** `what` ("Fetching settings…", "Fetching facts…", "Fetching the app…"), `shape` (`dot-line`, `rows`), `elapsed`.
- **Shapes:** `dot-line` is a still Dot at rest and one sentence; `rows` is three still `--surface-sunken` rows under the sentence. No spinner, no shimmer, no pulse.
- **States:** loading → (after 3s) "Still reading. 4s." → (6s) "Stalled?" and the owner link → (10s) timeout with Try again → loaded or failed. Settings, Memory and Discover show it for 300ms on first entry per session only. The fallback owner link is present from the start.
- **Reduced motion:** same.
- **Announcement:** the sentence isn't announced on its own; the result is.
- **Used by:** S2 frame, C3 Test, C4 Preview, C1 Discover, Memory, Settings, X1.

### Which screens use which

| Screen | Components |
|---|---|
| W1-W3 | DotMood (asleep, welcome, parcel, settled), OptimisticAction (connect), LiveTick (status row on phone), Toast |
| H0 | DotMood (asleep), Counter |
| H1 Home | ServiceCard (slip), LiveFactRow (peek), FreshnessBadge, Counter, DotMood (rest, nod, goodbye), ChangeRipple, LiveTick, Toast, OptimisticAction (disconnect, Undo) |
| C1-C6 | Skeleton, OptimisticAction (publish), DotMood (rest, parcel, settled), FreshnessBadge (preview), Toast |
| S1 | LiveFactRow, FreshnessBadge, ChangeRipple, DotMood (curious on Stale), OptimisticAction (rename, change shown), Skeleton |
| S2 | Skeleton |
| N1 | ServiceCard (card), Counter, ChangeRipple, Toast, (empty: `scene-quiet`, no Dot) |
| N2, D1, R1 | OptimisticAction; no Dot |
| M1 | LiveFactRow (card), ServiceCard (heading), ChangeRipple, Skeleton, DotMood (rest, asleep, peek) |
| T1-T8 | ServiceCard (row), OptimisticAction, Skeleton, LiveTick (T4), DotMood (rest; welcome in Help), Toast |
| X1 | Toast, Skeleton, DotMood (tucked), LiveTick (offline) |


## 2. What this design is

One Worlds, one flow, from an empty counter to a counter that keeps working: welcome, connect a service, preview it, publish it, watch facts change and age, follow a link out to the owning system, disconnect, revoke, and be back at an honest empty counter.

**Chosen base: V2 "Welcome-led Counter"** (Rylee: "V2 is the only one that passed"), grown to the full application using the Field Guide structure, the Rylee-Bee house tokens (Mulberry & Mint), and the Connect contract with Sol's six pre-prototype conditions.

### Deliberate changes from V2 (so reviewers can find them)
| # | Change | Why |
|---|---|---|
| 1 | Connect is a **destination page** (desktop, tablet) and a full-screen stepper (phone), not a modal dialog. | Back-button, deep links and focus order. V2 and Concept 5 already agree Connect is a destination in the nav. |
| 2 | **Needs you** is its own destination. | The Field Guide skeleton names it; it is also where the Project Home handoff lives (Sol condition 1). |
| 3 | The line "Mock handoff recorded; Worlds locked nothing." and the "Hand off to Home" button are replaced. | "Handoff recorded" reads as if an approval path works. It does not yet (condition 1). Replacement: an **owner link** ("Open Home app") and a separate **approval handoff** that honestly says "Approvals aren't connected." |
| 4 | **Disconnect keeps the credential reference** and has no tick to remove it. Removing the reference is a separate **revoke** with its own confirmation. | The Connect contract separates `disconnect` (reference retained) from `revoke` (config deleted, held credentials purged). V2 deleted the reference on disconnect. |
| 5 | Status chips say **"Needs you"** (LANGUAGE.md human label for `needs_attention`) where V2 showed the fixture `stateLabel` "Needs a human". | LANGUAGE.md owns the human labels; the fixture's `attentionReason` is still shown verbatim. |
| 6 | Page and section titles use two Worlds-local display handles composed from `--type-h1` (§6); no `clamp()`, no loose `calc()` in the build. | The house says a heading ladder past `h1` is a product's typographic decision composed from the shared tokens (`house/DESIGN.md`). V2's *source* used untokened `calc()` multiples of `--type-h1` where its design asked for a composed handle; this spec keeps V2's size step and names the handle. |
| 7 | Discover can name **every** not-yet-connected fixture service, shown honestly as "Not connected · no reading". | The proof path needs stale and unknown reached through a service the person actually connected. |
| 8 | The receipt is per **fact**, with a fact list above it, not only the first fact. | V2 showed `facts[0]` only. |
| 9 | The welcome is V2's single broad card, then earns **two** connections one at a time, with the parcel each time; the fact-journey is a note reached after the first connection. | Keeps V2's named onboarding signature, and makes "Connected in first run" true of something the person watched. |
| 10 | Services are **instances** of a kind (own id, owner-chosen name), not fixed fixtures; Settings gains **Activity**, **Help** and **For reviewers**; phone Settings is a list of pushed screens. | Round 1 (checklist MP-01, MP-17, MP-19, MP-23): a daily-use app needs two of a kind, a record of what changed, and somewhere to learn the words. |

### Inputs honoured
`docs/vnext/full-design-brief.md`; V2 and Concept 5; Field Guide docs; house tokens and `LANGUAGE.md`; the Connect contract `docs/vnext/connect/connect-contract.md`; `concept-brief-v2.md` requirements 1-6 and `concept-brief-v3.md`; the fixture. Rylee's standing preferences: dark by default with soft contrast, reduced motion respected, full keyboard support, 44px targets, plain words.

## 3. Information architecture

Worlds is the **Experience** layer: a costume over the stable skeleton. Platform contracts (the Connect contract) and Capabilities sit beneath it and do not change when the costume does ("Stable meaning. Mutable form."). The skeleton's four doors stay recognisable; Worlds gives each a counter-and-Dot form.

| Worlds destination (nav label) | Field Guide door | What lives here | Why it sits there |
|---|---|---|---|
| **Home** ("Your counter") | **Home**: orientation, what matters now | Status line, service slips, selected service, its facts and receipt, its app frame. The welcome lives here until done or skipped. | Home answers "what matters right now?" The counter is the Worlds form of that. |
| **Connect** | **Explore**: looking around, trying, synthesising | Discover, reference, safe test, preview, choose, publish. | Connecting is exploring what a service offers before committing. See Q1: the Connect *contract* is Platform/Capability; only this screen is Experience. |
| **Needs you** | **Needs You**: consequential human decisions | Services that need a person, owner retries, inert proposals, and the handoff to Project Home. | Authority stays with the human via Project Home's boundary. Worlds shows and links; it never decides. |
| **Memory** (page title "Agent facts") | **Guide**: understanding and continuity | Every shared fact from every connected service, as a **trail**: each service heading links to its owner, each fact says where it came from, who can see and act, and, for Unknown, what would help. | The Guide door's job is to leave a followable path. |
| **Settings** | not a door; a utility reachable from all four | Connected services, credential references, providers, live feed, motion and appearance, activity, help, about, and (collapsed) reviewer controls. | Settings is about the person and the install. On desktop and tablet it sits apart at the rail's foot. On phone it is **not a tab**; it is reached from the page header of every screen (§5.3), so the four doors stay the whole bar. |

Rules:
- **Skeleton words stay out of the way.** Nav labels are Worlds words and plain words. The mapping above is for the team, and for Help, which lists the four doors in one line each (Home = Your counter, Explore = Connect, Needs You = Needs you, Guide = Memory) with a link to the Field Guide. No screen is headed with a skeleton word.
- **Dropping the costume must not break the product.** Every destination works with Dot, the stamp and the parcel removed.
- **A service is not a destination.** A service's surface is a *view* inside Home (and linked from Needs you and Memory). It is opened by choosing its slip.
- **Order of nav:** Home, Connect, Needs you, Memory, then Settings (rail foot on wide screens; header link on phone). "Needs you" shows a count badge with its number in text (for example "Needs you, 1"). The number counts **decisions waiting**, not services; each Needs you service in the fixture holds one, so today it reads the same. It caps at "9+".
- **A service is an instance.** Its id (`media-shelf`, `media-shelf-2`) is what routes, filters and checker ids key on; its name is the owner's (rename, up to 40 characters); its icon comes from its kind, with a generic icon when a kind has none.

### Deep links (prototype routes, for back button and focus)
`#/welcome/1-3`, `#/home`, `#/home/{service-id}`, `#/home/{service-id}/{app}`, `#/connect/{step}`, `#/needs-you`, `#/memory`, `#/settings/{section}` (sections: `services`, `references`, `providers`, `live`, `activity`, `help`, `about`, `reviewers`), `#/owner/{app}` (the in-app stand-in for an owner link, so middle-click and "open in new tab" land on a Worlds screen, never on a browser error). Browser Back moves one screen and closes an open dialog or sheet first; focus returns to the control that opened the screen. The document title follows the route ("Memory · Worlds · MOCKUP") with "(1) " in front while a decision waits.

## 4. Every screen and state

Conventions: **Carries** names which protected-feeling items (§1) a screen keeps. State words use the closed vocabulary mapped in LANGUAGE.md: Healthy, Needs you, Stale, Unavailable, Unknown, Not configured (and Working, Done, Failed for the connect test). A state always has a word; colour, glyph and Dot are supplemental.

### 4.0 Screen inventory and what each carries

| ID | Screen | Route | States covered | Carries (items from §1) |
|---|---|---|---|---|
| W1 | Welcome card | `#/welcome/1` | default, skipped, replay | 1, 2, 4, 6 (asleep), 12 |
| W2-W3 | First and second connection | `#/welcome/2-3` | default, skipped, parcel | 5, 6, 7, 8, 11, 12 |
| H0 | Empty counter | `#/home` | first run, after skip, after last disconnect | 1, 2, 4, 6 (asleep), 9 |
| H1 | Counter, composed | `#/home` | quiet, needs-you, stale, unknown, unavailable, offline, searching, filtered to nothing, many services (20+), undo window | 1-6, 9, 10, 13 |
| C1 | Connect: Discover | `#/connect/discover` | loading, can't look, empty list, candidates, already-connected ×n | 1-5, 6 (rests), 11 |
| C2 | Connect: Reference | `#/connect/reference` | pristine, dirty, valid, not-a-reference, refused-secret, refused-own-secret, pending, save failed, replace (from a refused service) | 1, 2, 11 |
| C3 | Connect: Test | `#/connect/test` | idle, running, still reading, stalled, passed, failed, retry n of 3, limit, offline | 6 (static, awake), 11 |
| C4 | Connect: Preview | `#/connect/preview` | loading, stages, stalled, facts, empty, failed | 5, 6 (static), 11 |
| C5 | Connect: Choose | `#/connect/choose` | all, some, last-one-locked | 2, 11 |
| C6 | Connect: Publish and Connected | `#/connect/publish` | confirm, delivering, done, failed (rolled back) | 5, 6 (parcel, settled), 7, 8, 10, 13 |
| S1 | Service surface | `#/home/{id}` | facts, app, agent view (phone tabs), renaming, refused, zero facts, many facts | 1-5, 6 (curious on Stale), 10, 11 |
| S2 | App frame | within S1 | loading, loaded, refused, timeout, cancelled | 2, 11 (quiet otherwise) |
| N1 | Needs you | `#/needs-you` | items, new item, recently cleared, owner retries, sample proposal, empty | 1, 2, 11; **quiet**: no Dot anywhere, including the empty state (`scene-quiet`) (9) |
| N2 | Approval handoff | sheet or panel | not available (default) | 11; **quiet** |
| D1 | Disconnect | dialog or sheet | confirm, working, done | 11; **quiet**; Dot falls asleep only when the counter becomes empty (6) |
| R1 | Revoke | dialog or sheet | confirm, working, done | 11; **quiet** |
| M1 | Memory (Agent facts) | `#/memory` | loading, rows, collapsed, empty, filtered, filtered to nothing, service with no facts | 1, 2, 5 (fact rows), 6 (rests in header), 9, 10 (rows settle when a change lands), 11 |
| T1-T8 | Settings sections: services, references, providers, live feed, **activity**, **help**, about, for reviewers | `#/settings/{section}` | each with loading, empty, error | 1, 2, 6 (rests in header beside the live line; welcome in Help), 11 |
| X1 | Offline, error, loading | overlays and full-page wells | offline strip, offline well, failed to load, saving error, still reading | 11, 13; Dot rests in the header, tucked in the full-page wells only |

**Every list has an empty state**, in the same dashed well, one line, no blame:

| List | Empty state |
|---|---|
| Counter (H0) | `dot-asleep` in the well beside the `empty-counter` scene. "Quiet here." |
| Home, filtered to nothing | `dot-peek`. "No matches." and "Clear filter" |
| Needs you | `scene-quiet`, **no Dot**. "Nothing needs you." / "It'll show here." |
| Memory | `dot-asleep`. "No facts yet. Connect a service." |
| Memory, a service with zero facts | under its heading: "No facts. {emptyReason}" and its owner link |
| Memory or Settings, filtered to nothing | `dot-peek`. "No matches." |
| Discover, nothing left | "Add another of a kind you have." (every kind stays listed, "Already connected ×n") |
| Settings > Connected services, References | "Quiet here. Connect something?" / "No references. Connecting adds one." |
| Settings > Activity | `empty-ledger`. "Quiet so far." |
| Held, unused (references) | `empty-ledger`. "Nothing held." |
| Agent view tab, zero facts | the same dashed well with the fixture `emptyReason` |
| Owner retries | the section is hidden, not empty |

**Where the new art goes.** `dot-peek`: filtered-to-nothing wells. `dot-tucked`: full-page offline and "Couldn't load this" wells only. `dot-settled`: beside "{Name} is here." after the stamp. `scene-quiet`: Needs you's empty state (no Dot, the quietest screen). `empty-ledger`: Activity and held-reference empty states. `icon-generic`: any service whose kind has no icon of its own. Painted art is decorative (`alt=""`); a sentence beside it carries the meaning.

### 4.1 Welcome (W1-W3) and the first run

First run opens on Home with the welcome card in the main area; the shell (top bar, nav) is already there, so nothing is hidden and "skip" is genuinely a skip. `#skip-welcome` is on **every** beat and goes to H0 (or, after a connection, to the counter as it stands).

| Beat | What it shows | Primary action | Carries |
|---|---|---|---|
| **W1 Welcome** | V2's one broad raised card in a sunken well: **sleeping** Dot, the heading in `--wv-display-page`, two plain sentences about what Worlds is, one invitation. | "Connect a service" (to W2) | 1, 2, 4, 6, 12 |
| **W2 First service** | A compact connect for **Media Shelf** (the first service). Shows its name, kind and owner; the scope sentence ("Reference used only to read: …") with its capability ticks already on; a static one-line test result ("Passed. Nothing on Media Shelf was changed."); then one button. Dot wakes, carries the parcel (400ms desktop, 300ms phone), and the **Connected** stamp lands beside Dot. | "Connect Media Shelf" | 5, 6, 7, 8, 11 |
| **W3 Second service** | The same compact connect for **Front Door**. After the second parcel, the card closes and the counter appears with both slips; Front Door is selected. | "Connect Front Door" | 5, 6, 7, 8 |

The welcome's connections write the same records a full Connect run writes, with the reference handles `ref://media-shelf` and `ref://front-door` (labelled mock handles, **scoped**) and the provenance line "Connected in first run · reference held, never the secret." No real network is called, and each beat says so.

**After the first connection**, the first time a receipt is opened a dismissible note (not a beat, never blocking) draws "How one fact travels": Media Shelf, "Items in library: 1,284", as the three stations Source (Media Shelf, local), Worlds (shared as "Items in library"), Agent / Human. One sentence: every fact says where it came from and who can act. It carries 5 and 10 and is reachable again from Settings > Help. It is always about Media Shelf's first fact: reopening it selects Media Shelf first, or shows the same example statically if Media Shelf isn't connected.

Each beat carries a quiet "1 of 3" and the status row with `#live-toggle` and `#simulate-change` (phone included). One Back per beat. **Replay** (Help > Replay the welcome) runs the beats against a throwaway copy, labelled "Replay. Nothing changes."; it never touches real services, their facts or their kept-out choices.

Rules: no countdowns, no auto-advance; "Back" from W2 and W3; the welcome is never shown again after finish or skip (stored in the mock session; **Settings > Help > Replay the welcome** brings it back). Skipping on W2 or W3 leaves whatever was already connected in place. Reduced motion: no Dot movement; the parcel and stamp appear in place.

### 4.2 Empty counter (H0)

Shown after skip, and again whenever the last service is disconnected. This is "back to empty".

- Dot **asleep** in a dashed-outline well, beside the `empty-counter` scene; heading "Quiet here"; one sentence; `#add-service` (also in the top bar).
- Status line: "Nothing connected."
- Selected-service strip: "Nothing selected." with `#disconnect` visible and **disabled** (`aria-disabled`), with the reason "Connect something first" as visible text, and `aria-describedby` pointing to it.
- Local Weather is **not** shown as a slip. It has no facts and is not connected; it appears in Settings > Providers as Not configured.
- Memory shows its own empty state; Settings shows empty lists (same sentence).

**Carries:** 1, 2, 4, 6 (asleep), 9.

### 4.3 Home: the counter, composed (H1)

**Initial settled set:** after the welcome, Media Shelf (Healthy) and Front Door (Needs you), `media-shelf` and `front-door`. Front Door is selected on load, so `#disconnect` reads "Disconnect Front Door" on the first screen after the welcome. If the welcome was skipped, the counter starts empty (H0) and there is no settled set.

Order (reading order and DOM order are the same):
1. Page header: "Your counter" (`--wv-display-page`), with Dot resting beside the freshness line.
2. **Status line:** "1 needs you · checked 24s ago", with the live and simulate controls (see §5 for where they sit per width). The count is decisions waiting ("2 need you"); the count word is bold. Live reads "Live · checked 24s ago", or "Live · none current" when the freshest check is older than twice the re-check interval; when the oldest check is over an hour older than the freshest it adds "oldest 8h". It never says Live beside a number over 60s without that qualifier.
3. **Find, filter, sort** (only once more than 6 services are connected, so the quiet case stays quiet): a "Find a service" field (name, kind, owner app, fact label); state chips All · Needs you · Stale · Unavailable · Unknown, each with its count in text; a Sort select: Needs you first (default), Name, Recently checked, Newest. A result announces once: "3 of 12." Nothing found: the dashed well with `dot-peek`, "No matches.", "Clear filter". Filter and sort are remembered. DOM order is visual order; Dot doesn't react to sorting.
4. **Slips** (one per connected service). Each: icon; name; kind; state chip (glyph + word); the fixture **summary** or `attentionReason` as the reason line; one peeked fact (small label, value as the lead, or "No facts"); a line such as "1 stale." whenever any fact's own state differs from the service word (the peeked fact carries its own chip and "last known"); "checked 24s ago". Selected slip shows the word "Selected" and a check shape plus the mint border (never colour alone). Over 12 services, slips group under state headings ("Needs you · 2", "Healthy · 14") as collapsible sections in sort order.
5. **Service detail**: header (name, state chip, owner app, `#disconnect`), **fact list**, the **receipt** for the selected fact, the **Agent sees** line, then the **app frame** (secondary).
6. Dot at rest beside the freshness line, and "Updated now" with a nod when a state word changes.

**Many services (20+).** On desktop the slips column scrolls on its own and the detail pane stays sticky beside it. Where the list stacks above the pane (tablet, narrow desktop), choosing a slip scrolls the detail heading into view and a one-line sticky "Selected" bar (name and chip) stays at the top. Nothing about the quiet case changes. A reviewer control makes 24 services so this can be judged.

State presentation on a slip and in the detail. **The fixture's own sentence is always shown**; any Worlds explanation goes *under* it, never in its place.

| State | Chip | Slip reason line (fixture text, verbatim) | Worlds' added line | Value shown |
|---|---|---|---|---|
| Healthy | check + "Healthy" | `summary` | none | the value |
| Needs you | alert triangle + "Needs you" | `attentionReason` first, then `summary` | none | the value |
| Stale | clock + "Stale" | `summary` (for Nightly Backup: "Last good backup is past its daily window.") | "No change seen since {time} UTC." (for a simulated stale the fixture `summary` still comes first and this line goes under it; it stands alone only where no fixture sentence exists) | last known value, labelled "last known" with its checked time |
| Unavailable | x in circle + "Unavailable" | `summary` | per-cause line (§4.9) | "Unavailable" for a fact with no value; last good value kept and labelled |
| Unknown | question mark + "Unknown" | `summary` and `unknownReason` | "No current reading. Not guessing." | "Unknown" (never blank, never 0) |
| Not configured | dash + "Not configured" | `summary` | none | none; no placeholder |

**Quiet.** When the attention count is 0 the status line reads "Nothing needs you." Healthy and current are said in words, with no celebration. After `#simulate-change` with nothing else outstanding: "Last one done. Nothing needs you." **Carries:** 1-5, 9, 10.

### 4.4 The Connect lifecycle (C1-C6)

Connect follows the contract's verbs in the order the person meets them: **Discover → Reference → Test → Preview → Choose → Publish**, then the **Connected** moment. It is one page with a step list (vertical on desktop, a "Step 3 of 6 · Test" line on phone). Every step has Back; Cancel returns to Home without changes; nothing is saved until Publish (discover and test write nothing; the contract's `register` and `publish` are what persist). No real network is called in the mock, and every step that would call one says so.

**Two different ticks, two different contract fields.** Step C2 binds the credential's **send scope**: which *capabilities* the reference may be sent to (the contract's `CredentialReference.scope`, checked before Worlds dials). Step C5 sets the **publish selection**: which *facts* appear on the counter and to agents. They are never the same list and each screen says which it is.

**Proof-path services.** Discover can list: Notes Sync (the default first stop), Nightly Backup, Garden Camera, Studio Printer, plus anything the person disconnected or revoked. Local Weather is not listed in Discover: it is Not configured and belongs to Settings > Providers, whose "Connect" link opens Connect with it preselected (the way to reach a service with zero facts). Every kind stays listed, with "Already connected ×n" beside any that is at the counter; picking one makes a **new instance** (`media-shelf-2`, named "Media Shelf 2" until renamed). Services at the counter are also listed under "Already at the counter". Discover shows **no state word and no reading** for a candidate, because Worlds has not read anything yet.

| Step | What the person does | What Worlds says it will and won't do | Carries |
|---|---|---|---|
| **C1 Discover** | Picks a service from the candidates. Each shows name, kind, owner app, "Not connected · no reading", and the capabilities it is said to offer, each marked "unverified". Authentication need reads "Auth: unknown" (never a silent "none"). | "Looking only. No reference has been used yet. This sends no credential and changes nothing." Candidates are proposals, not facts: each shows who says it exists. | 5 |
| **C2 Reference (send scope)** | Enters a **credential reference**, not a secret, and ticks which **capabilities** the reference may be sent to (one checkbox per discovered capability, at least one, default all). | The reference is checked for shape when the person leaves the field. Worlds shows the scope sentence *before* any test: "Worlds will send this reference only when reading: {capability list}." plus "This is about what the reference can be used for. It is not what appears on your counter." Next stays disabled until the reference is valid and at least one capability is ticked. | 11 |
| **C3 Test** | Presses "Run safe test". It cannot run without a valid, scoped reference. | One read, nothing changed on the owning service. The reference is sent only within scope. Static progress ("Testing…", no spinner). Passes first time by default; a labelled mock checkbox "Simulate a failed test (mock)" makes it fail. | 6 (static Dot, awake) |
| **C4 Preview** | Reads what the service offers, now actually read. | Facts appear with their own states and are never merged: for Notes Sync, "Provider reachable: Unavailable", "Local notes waiting to upload: 3 notes, Live", "Last successful sync: Stale". Capabilities now read "verified". | 5 |
| **C5 Choose (publish selection)** | Ticks the **facts** to show on the counter. | At least one must stay ticked. Plain sentence: "Shown, and visible to agents: {list}." Anything unticked is kept out and named later as "kept out". | 11 |
| **C6 Publish** | Presses "Publish". | Shows the summary, then Dot carries the parcel (400ms desktop, 300ms phone), then the **Connected** stamp lands and the slip appears. Offers "Open {service}", "Add one more", and "Manage reference in Settings". | 7, 8 |

**C2 Reference field states** (pristine, dirty, valid, refused, pending):
- **Pristine:** "Use the form ref://name."
- **Dirty:** "Checked when you leave the field."
- **Valid:** a check shape and "Looks like a reference."
- **Not a reference (harmless):** a malformed but safe string (for example `ref://notes sync`) gets "Not a reference. Use ref://name." and **stays in the field** so it can be fixed. Names after `ref://` run to 49 characters, shown as a live "n/49".
- **Refused (looks like a secret):** a string with a secret's shape (a token prefix such as `sk-` or `ghp_`, or a long hex or base64 run) is refused. It is checked on blur **and on paste**. The field is **cleared at once**, the secret is never put into any message, announcement or stored state, and the message says nothing was saved. This answers the contract's "no secret value round-trip into the browser". This state is quiet: no Dot, no flourish.
- **Refused (Worlds' own secret):** a reference to one of Worlds' own secrets (names beginning `PW_`, `OIDC_` or containing `BOOTSTRAP`) is refused with its own sentence.
- **Pending:** "Saving…" static, field read-only. If the save fails: "Couldn't save. Nothing was changed." and the field is kept.
- **Replace** (from a refused service, or Settings): the same field, empty, reached by "Replace reference"; it runs the same checks and the safe test, clears the refused state only when the test passes, and otherwise keeps the old reference and says why.

**C3 Test states**: idle, running (static), **passed** (what was read, how long it took, "Nothing on {service} was changed"), **failed** (specific reason from the fixture `lastError`, for example "provider timed out"; the reference stays in the field; "last tried {n}s ago"; "try {n} of 3"; "Try again"; recovery text), and **limit reached** after three tries ("Run safe test" disabled with `aria-disabled` until the reference is edited). The failure never blames the person.

**C4 Preview states**: loading (static Dot, "Fetching facts…", naming its stage: "Reading." then "Shaping facts.", and "Reading 2 of 3 facts" when the count is known), still reading (after 3s "Still reading. 4s."), stalled (at 6s the owner link appears, not before; at 10s "Too slow." with Try again), facts, failed ("Couldn't read. Nothing changed. Try again." with the owner link), and empty ("No facts yet. Nothing guessed.", reached through a service with zero facts such as Local Weather from Settings > Providers). C3 gets the same still-reading and stalled words.

**C6 outcomes.** Optimistic: the new slip is in the counter behind the Connected card the moment Publish is pressed; the parcel and stamp settle it, and `dot-settled` stands beside "{Name} is here." Afterwards the service's receipt says, in its Worlds station, "Connected {when} · reference held, never the secret." A failed Publish (reachable from For reviewers) leaves the slip for 900ms, then removes it and returns to Publish with the reference and the chosen facts kept: "Didn't publish. Nothing was added. Try again." (assertive, once; no Dot). C6's summary names what will be published; the contract's `board` is not shown (Q10). The first fact published through Connect is also the one that is armed to go Stale then Unknown (§9), so the proof path can be walked on a service the person connected.

**Every step can fail, and stays recoverable.** A reviewer control, "Make the next Connect step fail", takes a step. In every case the reference and chosen facts survive, Back works, Cancel asks nothing, and nothing is saved until Publish.

| Step | Failure | What shows |
|---|---|---|
| C1 Discover | can't look | "Couldn't look. Nothing changed. Try again." |
| C2 Reference | secret, own secret, not a reference, save failed | as above |
| C3 Test | fails ×3; times out; reference refused | cause from the fixture `lastError`, else a classed line ("Provider timed out.", "Reference refused.", "Unreachable."); never a provider's free text |
| C4 Preview | can't read, stalls, empty | as in C4 states |
| C5 Choose | nothing ticked | the last tick is locked, `aria-disabled`, "Keep at least one." (the welcome behaves the same) |
| C6 Publish | fails | rolled back, as above |

Work the person leaves (Back, Escape, a route change) is cancelled; it never announces afterwards. While offline, Test, Re-test, Publish and Replace are `aria-disabled` with the reason "Offline."

**Leaving the flow:** Cancel, browser Back and Escape on the step page ask nothing when nothing was saved. If something was typed or ticked, the first Escape stays on the page and says "Nothing saved yet. Escape again to leave."; Cancel leaves at once. Steps change with a 150ms fade. The step page's header carries Dot at rest and the freshness line like the other working screens.

### 4.5 A service's surface (S1)

Inside Home, with Worlds navigation, the MOCKUP label and a back path visible around it. On desktop it is the right-hand detail pane; on phone it is a pushed screen.

Order: **header** (icon, name in `--wv-display-page`, kind, state chip, "Owned by Home", freshness, `#disconnect`; a curious Dot beside the chip when the service is Stale; **Rename** inline: field "Name", up to 40 with a live "n/40", Enter saves, Escape cancels, empty keeps the old name, "Renamed to {name}.") → **fact list** (compact rows; choose one) → **receipt** (the hero) → **Agent sees** line → **owner retry** (where the fixture offers one, §4.8) → **app frame** (secondary strip) → **kept out** note if the person left facts out in Choose ("1 fact kept out. Your choice." naming them: "Kept out: Guest code last used by.") with **Change what's shown**, which reopens C5 with the current ticks and applies the change in one pass. Zero facts: no list, the fixture `emptyReason`, and the owner link.

**The receipt (daily signature).** Three stations in a row (stacked on phone):
- **Source:** who produced it ("Home app said **unlocked**"), source word (local, external or none), state word, "checked 24s ago".
- **Worlds:** "Shared as Back door." The fact id, freshness word, and the provenance row ("Connected in first run · reference only, never the secret", or "Connected {when} · …"). Also the reference's **send scope** word: "Scoped to {n} capabilities" or "Unscoped" (see §10).
- **Agent / Human:** two separate labelled lines, **Agent can** and **Human can**, each with its action word in plain terms (see §7), and the fixture reason where there is one. A `none` permission is a **named, focusable, disabled control** carrying its reason (`aria-disabled`, not removed).

When a change lands, the stations re-settle in order Source → Worlds → Agent / Human, 60ms apart, with a tick at each, and "Updated now" (with Dot's nod) appears for 3s.

**Fact list rows.** Label (small), value (the lead; or Unknown / Unavailable), state word, "checked {time}", and "changed {time}" where the owner reported a change. Units are pluralised ("1 job"). Over 12 facts the list scrolls in its own box with "Show all 40", and choosing a fact scrolls its receipt into view. A non-Live fact offers "Check now"; a refused service offers "Replace reference" and "Open Memory app" beside the Source station. Every reference row (Settings and here) offers "Test again", which opens the C3 panel inline. For Front Door: Back door (unlocked, Human can act, reason shown), Unlocked for (47 minutes), Guest code last used by (visitor-3, Agent can't see it, reason shown). For a service with no facts (Local Weather, if ever shown): no rows and the fixture `emptyReason`.

The receipt is the hero: more padding than the rows around it, the 2px frame, and the value in `--type-h1`; fact rows are lighter than slips and receipt, so the eye goes slips → receipt → facts.

**Phone:** three buttons with `aria-pressed` (not a tablist): **Facts** (list and receipt), **App** (frame and fallback), **Agent view** (that service's rows as in Memory). Facts is selected on arrival; inactive panes are `hidden`.

### 4.6 The embedded app frame (S2)

A bordered, labelled frame ("Home app, shown here") holds the owning app, below the receipt. The fixture owners and fallbacks are used exactly: "Open Media app" → `app://media`, "Open Home app" → `app://home`, "Open Memory app" → `app://memory`, "Open Provider settings" → `app://settings/providers` (Local Weather). In the prototype an `app://` link cannot navigate. It is drawn as a link to `#/owner/{app}`, so middle-click or "open in new tab" lands on a Worlds screen, and an ordinary click opens a small non-modal note anchored to the link, "This would open {app} outside Worlds" (Escape closes it and returns focus to the link; from the handoff panel the panel stays open underneath). No dead link exists.

| State | What shows | Controls |
|---|---|---|
| **Loading** | Static Dot and "Fetching the app…" in the frame; the fallback link is already present. | Fallback link; Cancel |
| **Loaded** | The contained app preview. Frame header names the owner app and the state word. Text under it: "No Worlds credentials in here." | Fallback link; Reload |
| **Refused** (the app can't be shown inside Worlds) | The frame body is replaced by: "Didn't load here." plus the cause if known ("It won't show inside another page") and "Use the link below, or try again." The slip, receipt, facts and state stay exactly as they were. | "Try again", "Open {app}" |
| **Timeout** | Same as refused, cause "Too slow." The hard limit is 8s. | same |
| **Cancelled** | "Cancelled." The rest of the surface is unchanged. | "Try again", "Open {app}" |

The frame starts loading only when the App pane is in view (on phone, when its tab is chosen), so a hidden pane never spends a try. A reviewer control, "Make the next frame fail: refused / slow / never", reaches each outcome on any service; by default the first two tries fail and the third loads, so "Try again" costs something and pays off. Build note: the real `<iframe>` carries `sandbox` without `allow-same-origin` and `referrerpolicy="no-referrer"`.

The frame never receives Worlds credentials, and any consequential action inside the app belongs to that app. Real sandbox rules and browser support are UNKNOWN (Q4). Worlds navigation, back and the status line keep working with the frame in any state.

### 4.7 Needs you (N1) and the Project Home handoff (N2)

**Needs you is where Worlds is quietest.** No Dot, no flourish, on item cards, the header or the empty state. An item that arrived while the person was on another screen carries a text mark, "New", cleared when they open it, and is announced once. The tab title gains "(1) " while a decision waits. There are no push notifications and no sounds: Worlds shows, never pesters.

**N1 items.** One card per service that needs a person (`needs_attention`). Front Door's card: name; chip "Needs you"; fixture summary ("Back door unlocked longer than usual."); fixture `attentionReason` ("A decision is required; the local app will not act on its own."); the facts behind it; and **two separate routes**, never merged:
1. **"Open Home app"**: the owner link (`app://home`). This is where the person decides. Always available.
2. **"Ask Project Home to review"**: the approval handoff. It is a link or handoff, never a button that "does" something. In this mock it is **fail-closed**: its state is "Not available yet", shown at all times in text beside it.

Services that are Unavailable and offer an owner retry (Notes Sync, Studio Printer) are listed below as **owner retries** (§4.8), not as approvals.

**N2 the handoff panel (fail-closed, the only state built).** Opening "Ask Project Home to review" shows, in a panel (sheet on phone):
- Heading: "Approvals aren't connected."
- Body: "Nothing sent. Decide in the Home app instead."
- Buttons: "Open Home app" (primary), "Close".
- A line stating the intended path: "Once connected, this opens Project Home. It decides, not Worlds."
- Never shown: "Sent", "Pending approval", "Approved", a spinner, or a recorded-handoff receipt.

**Design note for later (not built, not reachable).** A future "Link ready" state would say what will be opened, in which system, and that Worlds records no decision, with a real link. It must be *proven* connected; any other state, including "unknown whether approvals are connected", renders as the fail-closed state above. The prototype has no control, setting or UI path to this state (§10, §11).

**Recently cleared** (below the items, read-only, last 5, from Activity): "Front Door. Cleared 2:31 PM UTC. Home reported it."

**N1 empty:** `scene-quiet` (no Dot); "Nothing needs you." / "It'll show here."

### 4.8 Owner retries and inert proposals

Two different things, kept apart.

**Owner retries (fixture-true).** The fixture gives Notes Sync "Check provider now" (`probe-provider`, `allowed: human`, attempts 2, last error "provider timed out") and Studio Printer "Retry last job" (`retry-last-job`, `allowed: human`, attempts 1, last error "job rejected: no media loaded"). Worlds shows them as text with the attempt count and last error, and one route: a link to the owning app ("Open Memory app", "Open Studio app" using the fixture's owner link). **There is no Run or Retry button in Worlds.** The retry happens in the owning app, by a person. They are not approvals and are not proposals.

**Proposals (contract shape; the fixture has none).** The fixture contains no proposal objects, and this spec does not invent fixture-labelled ones. The proposal component is drawn from the contract's `ActionProposal` (`exposed: false`, effect, authority) and appears in the prototype **once, as an illustrative sample** on Needs you, clearly marked "Sample. The fixture has no proposals." Its fields: label "Sample action"; effect word "Changes something outside Worlds"; "Proposed. Not active."; "Decided by: not known yet" (bound to the contract's `authority`, shown as UNKNOWN rather than choosing Home or Project Home); and "Agent can't do this."
- **No Run, Do it or Approve control exists on a proposal.** The only controls are "Open Home app" and "Ask Project Home to review" (§4.7). A proposal row is read as text, not focusable as a command.
- `lock-back-door` appears only in its applied form (§9: the owning app reports it done). Worlds never shows it as a pending proposal.
- No agent can propose, adopt or run anything; an adopted external write is not an agent tool (`exposed: false`).

### 4.9 Stale, unknown, unavailable, reference refused, not configured

These are **states of the same screens**, not separate pages. Each keeps the last-known value visible and labelled, says when Worlds last checked, offers a route to the owner, and never promises recovery.

| State | Cause (mock) | What the person sees | What they can do |
|---|---|---|---|
| **Stale** | Fixture: Nightly Backup. Scripted: a live fact misses a re-check (§9). Real rule is UNKNOWN (Q6). | Chip "Stale" (with "(simulated)" for scripted ones). Fixture summary first; then "Nothing has changed since 2:23 PM UTC that Worlds knows of." Last value labelled "last known". Receipt Source station: "Last checked 3m ago." The slip carries the fact's own chip and "1 stale." even when the service word differs. Curious Dot beside the header chip. | "Check now" (on any non-Live fact; restores a scripted fact to Live in the mock), "Open {owner app}". |
| **Unknown** | Fixture: Garden Camera. Scripted: a stale fact left for 60 more seconds becomes Unknown (simulated). | "No current reading. Not guessing." plus fixture `unknownReason`. Value "Unknown" (never blank). Any last known value in its own labelled line. Agent can't assert (fixture reason). | "Open {owner app}". No retry is invented. |
| **Unavailable, provider silent** | Fixture: Notes Sync. | "Stopped answering. Last facts kept, with check times." Fixture summary and last error. | "Open Memory app" (owner retry, §4.8). |
| **Unavailable, job rejected** | Fixture: Studio Printer ("Last job failed. Printer reachable, job rejected."). | The fixture's own sentence, then "Printer answered, so not silent." Last error "job rejected: no media loaded". | "Open Studio app" (owner retry, §4.8). |
| **Reference refused** | The provider stopped accepting the reference (mock trigger in For reviewers). | Chip "Unavailable", reason "Notes Sync refused the reference." Last facts kept and labelled stale. The error is classed, not free text from the provider. | "Replace reference" (opens Connect at Reference, field empty; on the slip, the header and the Source station), "Open Memory app". Worlds cannot fix the provider's side. After a passing replace the facts return to Live with "Checking now" and then a real checked time. |
| **Not configured** | Fixture: Local Weather, never set up. | Chip "Not configured"; fixture summary; no facts, no placeholder. | "Open provider settings". |

**Disabled.** The fixture vocabulary lists `disabled`; Worlds never shows it, because no fixture service uses it. A chip given a state it doesn't know prints that word and never fails.

Rule: Stale and "waiting" are separate. A reassuring state never hides a stale one, and an unknown or unclassified case is shown as Unknown, never as fine. Unavailable text is chosen by cause; one sentence is never reused for a different cause.

### 4.10 Disconnect (D1) and back to empty

`#disconnect` is always visible for the selected service and opens a confirm that **names the service and says what goes and what stays**. It is a dialog on desktop and tablet and a bottom sheet on phone. It is a consequential surface: no Dot, no flourish. **Disconnect deliberately keeps the credential reference** (the contract's `credentials_retained`); nothing is deleted from anywhere but Worlds' counter. Removing the reference is a different action with a different confirmation (R1, §4.11).

| Goes (from Worlds) | Stays |
|---|---|
| The slip, its facts, its receipts, its app frame, and the kept-out note. | The owning app, untouched. Nothing is sent to it and nothing in it changes. |
| What Worlds has remembered of the last-known values. | The credential reference (held, nothing is sent with it), listed in Settings as "Held, unused". |

Buttons: **Disconnect** (danger) and **Keep service**. Escape = Keep service. Focus: opens on the heading; Keep service is the first button (a safe default); on close, focus returns to `#disconnect` or, after a successful disconnect, to the next slip (or to `#add-service` when none is left).

**Optimistic then settled:** the slip, facts and frame leave in the same frame the confirm is pressed; a status message then names exactly what went ("Notes Sync's 3 facts and its app frame are removed from Worlds. The Memory app is untouched. Its reference is kept."), with `dot-goodbye` beside it (outside the dialog), and offers **Undo** and "Reconnect".

**Undo.** A visible "Undo · 24s" lasts 30 seconds of mock time (text, counting down on the mock clock; pausing the feed pauses it). Pressing it restores the service exactly as it was (position, facts, selection, kept-out facts, frame) in one step, with Dot carrying the parcel back (mirrored; in place under reduced motion), and announces "{Name} is back." At 0 the snapshot is dropped and only "Reconnect" (Connect with the service and reference prefilled) remains. This is an in-session undo, not history: nothing is stored, and "Keep history after disconnect" stays undecided. Disconnect works offline ("Offline. Removed from Worlds."). If removal fails: "Couldn't remove that. Nothing was changed." If it was the last service: H0 (empty counter), Dot falls asleep (200ms, none under reduced motion). **Worlds still works:** Memory and Settings show their empty states; Connect still starts.

### 4.11 Revoke (R1)

Revoke is the contract's `revoke`: it deletes the connection's config, **purges the held credential reference**, and reports `external_state_untouched: true`. It is reached from Settings > Credential references > **Remove** (also on a "Held, unused" row). It is quiet like disconnect.

| Goes (from Worlds) | Stays |
|---|---|
| The credential reference and anything Worlds held for it. | The owning app, untouched. |
| The connection's config. If the service is still on the counter, it is disconnected as well, because it can't publish without its reference: its slip, facts, receipts and frame leave too. | **The provider's own key.** Worlds can't revoke it. The person should rotate or revoke it with {App}, the owning app. |
| The service becomes a Discover candidate again ("Not connected · no reading"). | Anything the owning app holds. |

Dialog: title "Remove {Name}'s reference?"; the table above in plain sentences; "Worlds can't revoke the key. Rotate it in {App}." Buttons **Remove reference** (danger) and **Keep reference**; Escape = Keep reference; focus as D1. After: "{Name}'s reference is removed and its connection is gone from Worlds. The key itself is still active with {App}. Rotate it there." plus "Open {App}". If this empties the counter: H0.

### 4.12 Memory: Agent facts (M1)

Memory is the **Guide** door: a trail, not a flat inventory. One list of every fact from every connected service, using the **same fact-row component** as S1, so one fact reads the same everywhere.

- **Service headings** carry the owner link ("Open Media app") and the service's state word and freshness, so a screen-reader user can jump by heading and a person can follow any fact to its owner.
- Each **row**: label, value (or Unknown / Unavailable), state word, source (local, external or none), "checked {time}", **Agent can** and **Human can** as two labelled lines, the fixture reason where there is one, and the send-scope word for the service's reference ("Scoped to {n} capabilities" or "Unscoped").
- **Unknown rows** add: "Can't see it. {fixture unknownReason} Needs the owning app to answer." with the owner link.
- A `none` permission renders as a named, focusable, disabled control with its reason.
- Filter: "All services" or one service (a select, keyboard reachable), plus "Find a fact" (label, value, owner) and the same state chips as Home. Services are collapsible sections (heading as summary), open when 6 or fewer are connected. Each fact row is one line (label, value, chip, age) with a disclosure for source, scope and permissions; **Unknown rows start open**. A service with zero facts shows "No facts. {emptyReason}" and its owner link. First visit per session shows a still "Fetching facts…" with three sunken rows for 300ms.
- When a change lands, affected rows settle with the same 60ms tick as the receipt (item 10). Dot rests in the page header beside the freshness line.
- **Empty:** the counter's dashed empty well with Dot asleep: "No facts yet. Connect a service." with `#add-service`.

**Who sees, who acts** words: a person reads "Agent can: see it" and "Human can: act on it in the Home app". Values and permissions change only by an event the owner caused (§9), never by Worlds on its own.

### 4.13 Settings (T1-T8)

Desktop and tablet: a section list beside **one** pane; only the routed section renders (`#/settings/{section}`), the list is real links with `aria-current="page"`. Phone: Settings opens on a list of the eight sections, and each is a pushed screen with Back in the top bar (Settings is reached from the header, which becomes Back inside it). Dot rests in the page header beside the live line. Sections, in this order:

1. **Connected services:** one row per service: name, state word, freshness, and in order **Rename**, **Test again**, its own `#disconnect-{service-id}` (same confirm as D1; text-weight danger). Search appears here too past 6 services. Empty: "Quiet here. Connect something?"
2. **Credential references:** heading line "References only, never secrets." Each row: service, the reference text (wraps, never truncated), **send scope** ("Scoped to {n} capabilities: {list}" or **"Unscoped (older connection): this reference can be used for anything this service offers"**), and in order Test again, **Change scope** (Connect at Reference, capabilities ticked, test re-runs on save; for unscoped ones the same control is labelled "Narrow scope"), Replace, Remove (opens R1). For an older connection with no stored capability list, Connect first runs the read-only Discover for that service and then lands on C2. The welcome's references (`ref://media-shelf`, `ref://front-door`) are labelled mock handles and are **Scoped**. To show the legacy label (Sol condition 3) a reviewer uses the For reviewers control "Pretend Media Shelf has an older, unscoped connection". Replace is an inline field with the same checks as C2 (validated on blur and paste, secret refused and cleared, never stored or logged), then "Saving…", then the safe test; it keeps the typed text and focus across any repaint. A kept reference from a disconnected service appears as "Held, unused". Empty: "No references. Connecting adds one."
3. **Providers:** every kind with no instance and no reading (today Local Weather): name and icon, Not configured, fixture summary and `emptyReason`, no facts, "Open provider settings" → `app://settings/providers`, and "Connect", which opens Connect with it preselected (that flow reaches the zero-facts states).
4. **Live feed:** `#settings-live` switch (the same state as `#live-toggle`; the two always agree); check cadence 5s (default), 10s, 30s (changing it restarts the cadence from now); **Times:** UTC (mock default) or This device; **Motion:** Follow system (default) / Reduce always; **Theme:** Dark (default), Light, High contrast, Low stimulation, Follow system; **Text size** note ("Worlds follows your browser's text size; zoom to 200% reflows"). Line: "Reduced motion removes animation, not data."
5. **Activity:** the session's event log, newest first, one line each ("2:31 PM UTC · Front Door · Back door locked. Home reported it."), times from the mock clock, "simulated" where simulated, capped at 200. "This session only. Nothing is kept after you disconnect." It is never stored, and "Keep history after disconnect" stays undecided. Empty: `empty-ledger`, "Quiet so far."
6. **Help:** short entries (two sentences at most) with Dot's `dot-welcome` in the header: "What are the words?" (the six state words with their glyphs, one line each); "What's a reference?" ("A name for a secret kept elsewhere. Worlds keeps the name only."); "Who can act?"; "The four doors" (Home = Your counter, Explore = Connect, Needs You = Needs you, Guide = Memory, with a link to the Field Guide); "How one fact travels"; "Replay the welcome" (a copy; "Replay. Nothing changes."); "Keyboard" (how to do every job without a mouse).
7. **About:** MOCKUP, "Synthetic data only", "Times in UTC.", "Mock clock starts at 2:24 PM UTC on Oct 13. Real time isn't used.", how Worlds fits the Field Guide (one sentence with links to the Field Guide map, this spec and the Connect contract), the UNKNOWNs (§12) as a short list, a disabled named "Keep history after disconnect" with reason "Not decided yet; this mockup keeps nothing", and "Stored in this browser: your settings and your services' names and references. Nothing else."
8. **For reviewers** (collapsed by default, its own heading, never beside Help): controls that only produce *failure or edge* conditions, each stating what it does: "Make Media Shelf stale now", "Pretend Notes Sync refused its reference", "Pretend Media Shelf has an older, unscoped connection", "Make the next Publish fail", "Make the next Connect step fail" (with a step), "Make the next save fail", "Make the next screen fail to load", "Make the next frame fail: refused / slow / never", "Go offline (mock)", "Simulate slow" (×8), "Make Studio Printer need you", "Home reports it unlocked again", "Make 24 services", and **Start over** ("Clears this browser's mock. Nothing else.", with a confirm). **There is no control here, or anywhere in the UI, that makes approvals look connected** (§10).

States per section: loading (a still Dot and "Fetching settings…", 300ms on first entry per session), empty (as above), error ("Couldn't save that. Nothing changed. Try again."; the field and its text are kept), long references wrap. Saves apply at once and roll back if they fail (OptimisticAction).

### 4.14 Offline, error, loading (X1)

- **Offline** (the browser has no connection, or the reviewer control): a strip under the top bar, "Offline. Showing what was last known, with times." The live feed pauses (`#live-toggle` reads "Paused · offline" and is `aria-disabled`; the person's own live or pause choice is remembered and restored), and ages stop growing (they would be false). **States keep their own words.** Worlds does not invent Stale for offline; each Live fact swaps "Live" for "Offline · last checked 3m ago". Actions that would call out (Test, Re-test, Publish, Replace) are `aria-disabled` with "Offline."; navigation, Memory, Settings and Disconnect keep working. On return: "Back online. Checking." until one re-check of every Live fact resolves, then "Checked just now." for 3s. In a full-page well (nothing to show), `dot-tucked` rests; the strip itself never carries Dot.
- **Couldn't load a screen:** "Worlds couldn't load this. Your services and references weren't changed." "Try again" and "Go to Home". `dot-tucked` at rest size in the well; no blame. A reviewer control makes the next screen fail so this can be walked.
- **Save failed:** "Couldn't save that. Nothing was changed. Try again." The person's text is kept.
- **Loading:** always static (a still Dot and a sentence, or three still sunken rows). No spinners, no shimmer. Waits add words only: "Still reading. 4s." after 3s, the owner link at 6s, a timeout with Try again at 10s.
- **Away:** back from a hidden tab after 60s, one line in the status area: "Away 4m. 1 thing changed." linking to Activity. Never a modal.

## 5. Layouts

Three layouts, designed separately. Breakpoints in rem so they follow text size: **desktop ≥ 60rem** (designed at 90rem, which is 1440px); **tablet 48rem to under 60rem** (designed at 48rem, 768px); **phone under 48rem** (designed at 24.375rem, 390px). DOM order equals reading order at every width; the layout changes by CSS, not by reordering content. No sideways scroll; at 200% zoom content reflows and nothing clips.

### 5.1 Desktop (1440)

- **Top bar** (sticky; its height is measured, never assumed, so 200% text can't hide content behind it): MOCKUP label and "Worlds"; then `#live-toggle` ("Live" / "Paused", with its age "checked 24s ago" / "frozen at 24s" in the text beside it, fixed width, tabular figures), `#simulate-change`, `#add-service`, `#disconnect` ("Disconnect Front Door", one line to 20 characters then an ellipsis, with the full name in its accessible name and `title`; text-weight danger, border on hover and focus; or disabled "Disconnect" when none).
- **Rail** (left, `--surface-sunken`): Home, Connect, Needs you (badge), Memory; Settings at the foot. Icon and label always visible.
- **Home:** two columns: slips (a column of roughly 23rem, scrolling on its own with the find, filter and sort row above it) and the detail pane (sticky). Pane order: header, fact list, receipt (hero), Agent sees, app frame.
- **Connect:** vertical step list at the left of the page, step body in the middle, a summary of what will happen at the right if width allows; Back/Next bar at the foot of the body.
- **Needs you and Memory:** single reading column up to a comfortable measure (about 55ch for prose), cards full width.
- **Settings:** a 14rem section list and the one routed pane.
- **Dialogs:** centred, `--surface-raised`, scrim `--surface-sunken`.

### 5.2 Tablet (768)

- Top bar wraps to two rows (title and live controls, then add and disconnect). The rail is a narrow strip with **icon above a short label, always visible** (hover does not exist on touch, so labels are never hover-only); the accessible name is the label. On keyboard focus a tooltip with the full name also appears.
- **Home:** slips become a two-column grid above the detail pane; the pane is full width; receipt stations stay three across (they fit at 768) and drop to a column under 40rem.
- **Connect:** step list becomes a horizontal numbered strip above the body.
- **Settings:** the section list becomes a wrapped row of links above the one routed pane.
- Targets stay 44px; gaps do not collapse.

### 5.3 Phone (390)

Own navigation and reading order, not a squeezed desktop.

- **Page header:** MOCKUP label, title, and a **Settings** text-and-icon button at the right (at least 44px) on every top-level screen (at 320px the icon, with the full name as its accessible name). This is the only route to Settings on phone; inside Settings and on a pushed service screen it becomes Back.
- **Status row:** the one-line status ("1 needs you · checked 24s ago") then `#live-toggle` and `#simulate-change` as two 44px-high buttons (wrap to two lines if needed).
- **Selected-service card:** state chip, reason, "Open Front Door" and `#disconnect` ("Disconnect Front Door") on the first screen. With none selected: the honest line plus disabled `#disconnect` with its reason.
- **Slips:** full width, each at least 44px, state word and freshness visible.
- **`#add-service`:** a floating 44px-high pill with a real border, at right 1rem, bottom `calc(<tab bar height> + env(safe-area-inset-bottom) + 1rem)`; the list has enough bottom padding so it never covers a slip. Shown on Home, and on Memory only when it is empty; hidden on Needs you, Settings, pushed screens and in Connect. The toast sits above it.
- **Bottom tab bar:** the **four doors**: Home, Connect, Needs you (with count in text), Memory. Four equal tabs, each at least 44px tall and wide (the bar is 3.5rem plus safe area). The tab bar is `aria-label="Worlds sections"`.

**Exactly one bottom strip at a time:**

| Screen | Bottom strip |
|---|---|
| Home, Needs you, Memory, Settings | Tab bar |
| Pushed service screen | none; Back is in the top bar |
| Connect | the sticky Back / Next bar (replaces the tab bar) |
| Dialogs (disconnect, revoke, handoff) | bottom sheet over the tab bar, scrim behind |
| Offline strip | top, under the page header (never a second bottom strip) |

**Narrow phones (320px).** Not the design width but held: the Connect bar wraps to two rows under 24rem (Next full width on top); fact rows stack label and age over value and chip; dialog buttons stack full width; tab labels may wrap to two lines; the rail badge sits at a fixed corner of its icon. At 200% text nothing clips and nothing scrolls sideways.

**Pushed service screen:** Back (top bar), the status row, then `#disconnect` under the heading, then tabs **Facts / App / Agent view**; Facts first; receipt first inside Facts. Focus moves to the new heading on every push and returns to the invoking slip on Back.

## 6. Components and tokens

Tokens are the house names in `docs/vnext/house/tokens.css`. **No colour, gap, radius or text size is written as a literal outside tokens or the local handles below.** Lengths that have no token (target floor, hairlines, panel widths, durations) are Worlds-local handles with a `--wv-` prefix, defined once, in `rem`; they hold no colour. (The tokens document is explicit that the target floor is Play-Nice's and has no token; Q8 asks whether these handles should be promoted.)

**Local handles (layout, not colour):** `--wv-target-min` (the 44px floor, as 2.75rem), `--wv-hairline`, `--wv-frame-line`, `--wv-ring-width`, `--wv-rail-w`, `--wv-slips-w`, `--wv-ease` (`cubic-bezier(.2,0,0,1)`), `--wv-dur-state` (150ms; 120ms phone), `--wv-dur-stagger` (60ms), `--wv-dur-sheet` (200ms), `--wv-dur-nod` (200ms), `--wv-dur-stamp` (280ms: scale 1.35 to 1, then a 40ms settle; the stamp is the one proud moment), `--wv-dur-carry` (400ms; 300ms phone), `--wv-icon-sm` (2rem) and `--wv-icon-lg` (2.5rem) for service icons, `--wv-pad-tight` (.125rem, the MOCKUP label's padding), `--wv-measure` (40rem), `--wv-panel-w` (14rem), `--wv-hero-w`, `--wv-scene-w`, `--wv-toast-w` and `--wv-station-min`; `--wv-top-h` is measured at run time. Reduced motion sets durations to 0 and travel to 0 (including `:active` nudges).

**Display handles (the product's typographic decision past `h1`, composed from `--type-h1` per `house/DESIGN.md`):** `--wv-display-page` (2.5rem) for page titles, service titles and the welcome heading; `--wv-display-section` (1.85rem) for section headings. Both are plain `rem`, aliasing upward from `--type-h1`; neither is fluid. They keep V2's roughly 2.5:1 display-to-body step, which is where the "printed, hand-labelled" air comes from. `--type-lead` and `--type-body` are used for everything else. One heading ladder: page title `--wv-display-page`; section heading `--wv-display-section`; the title of a card inside a list (a service on Needs you or Memory) `--type-h1` as `.h-card`; slip name `--type-lead`. No heading is sized by an inline style, and no padding, margin or gap is a `rem` literal outside `:root`; a page test checks both.

**The reactive pieces** (LiveFactRow, FreshnessBadge, ServiceCard, DotMood, Counter/badge, ChangeRipple, LiveTick, Toast + live region, OptimisticAction, Skeleton/loading) are specified once in "Reactive components"; the table below lists where each is drawn and the tokens it uses.

| Component | Tokens it uses | States |
|---|---|---|
| **App shell** (top bar, rail, tab bar, main) | `--surface-base` page, `--surface-raised` top bar and tab bar, `--surface-sunken` rail, `--border-line` edges, `--space-*` | wide, tablet, phone; offline strip |
| **MOCKUP label** | `--accent-mint` text and border, `--radius-sm`, `--type-micro` | always visible on every screen |
| **Status line** | `--text-soft`, `--status-needs-you` for the count word (bold), `--type-body`, tabular figures for ages | quiet, needs you, paused, offline, none current, away |
| **Live toggle / Simulate** (LiveTick) | button tokens; `aria-pressed` on the toggle; age text beside it in a fixed width | on, paused, offline (`aria-disabled`); simulate: ready, done (`aria-disabled`, reason visible), no Front Door (`aria-disabled`, reason) |
| **Button** (primary, secondary, danger, text, icon) | primary: `--action-primary`, `--action-on-primary`; secondary: `--surface-raised`, `--border-line-strong`, `--text-primary`; danger: `--status-failed` border and text; `--radius-full`; `--type-label` | default, hover, focus-visible (`--focus-ring`), active, disabled, pressed; at least `--wv-target-min` tall |
| **State chip** (FreshnessBadge) | `--status-*` text on `--surface-raised` or `--surface-sunken`, a glyph, the word, `--type-small` | healthy, needs you, stale, unavailable, unknown, not configured, an unknown word printed as itself; live, ageing, offline-qualified; never glyph or colour alone; a small "sim" pill (full word in `title` and hidden text) where simulated |
| **Slip** (ServiceCard) | `--surface-raised`, `--radius-lg`, `--border-line`, selected `--action-primary` border and the word "Selected"; icon in a fixed `--wv-icon-sm` square | default, hover (lifts), selected, focus, pending, removing, New, with stale/unknown/unavailable content and a "1 stale." line |
| **Page and service header** | `--text-primary`, Young Serif, `--wv-display-page` | per state; Dot rests beside the freshness line |
| **Section heading** | Young Serif, `--wv-display-section` | n/a |
| **Fact row** (LiveFactRow) | `--surface-raised`, `--border-line` (lighter than slip and receipt), `--type-lead` for the value, `--type-small` for the label | live, ageing, stale, unavailable, unknown; offline-qualified; permission none; settling; collapsed and open (Memory) |
| **Receipt** (ChangeRipple) | frame `--border-line-strong`, `--radius-lg`, `--surface-raised`, `--space-xl` padding; stations `--surface-sunken`, `--radius-md`; value in `--type-h1` | idle, updating (ticks settle), reduced-motion (all ticked at once), refused (Replace reference), zero facts |
| **Agent can / Human can lines** | `--text-primary`, `--text-soft` for reasons | read, act, write, none (disabled and named) |
| **Provenance row** | `--text-soft`, `--type-small` | welcome, connected later, unscoped, scoped |
| **App frame** | `--surface-raised`, `--border-line`, inner `--surface-sunken` | loading, still reading, loaded, refused, timeout, cancelled |
| **Owner retry row** | `--surface-sunken`, `--border-line` | shown with attempts and last error; a link only, no command |
| **Proposal row (sample)** | `--surface-sunken`, dashed `--border-line-strong` | proposed (inert); never active in this mock; carries a "Sample" word |
| **Handoff panel** | `--surface-raised`, `--border-line-strong` | not available (the only built state) |
| **Connect stepper** | progress uses `--action-primary` (done) and `--border-line` (to do); current step has a numeral, a word and `aria-current="step"` | pending, current, done, error |
| **Reference field** | `--surface-sunken`, `--border-line-strong`, error `--status-failed`, valid `--status-done`, each with a word and glyph | pristine, dirty, valid, refused, pending, disabled |
| **Send-scope list** (capabilities) | checkboxes on `--surface-sunken` rows | all, some, none (invalid) |
| **Test panel** | `--surface-sunken` | idle, running, passed, failed, retry n of 3, limit |
| **Fact chooser** (publish selection) | checkbox rows | all, some, last-one-locked (`aria-disabled`, with its reason) |
| **Dot** (DotMood) | shell `--accent-apricot`, body `--accent-mint`, ink `--surface-base`, parcel paper `--surface-raised` with `--border-line-strong` | rest, asleep, welcome, nod, parcel (and mirrored), settled, goodbye, curious, peek, tucked; `aria-hidden` except where a sentence names Dot; sizes rest 3.25rem phone, 3.75rem tablet, 4.75rem desktop, `lg` capped at 7rem |
| **Stamp** | `--status-done` border and text, Young Serif capitals, tilted -4°, padding for the tilt | landing (`--wv-dur-stamp`, 280ms), static (reduced motion: appears in place) |
| **Dialog / sheet** (disconnect, revoke, handoff) | panel `--surface-raised`, scrim `--surface-sunken`, `--radius-lg` | open, working, closed; Escape closes |
| **Toast / live line** (Toast + live region) | `--surface-raised`, `--status-done` border (a real border), one polite `role="status"` and one assertive `role="alert"`, created once | hidden, visible (`max(4s, 60ms × characters)`; longer while paused; pauses on hover or focus), queued, with Undo or Reconnect and Dismiss |
| **Empty state** | dashed `--border-line-strong`, `--text-soft`; art capped at 40% of the well, text keeps 28ch | first run, after disconnect, empty list (also Memory), no matches (`dot-peek`), Needs you (`scene-quiet`), activity and held (`empty-ledger`) |
| **Settings section, switch, select, radios** | `--surface-raised`, `--border-line-strong` | each with loading, empty, error; pane (wide) or pushed screen (phone) |
| **Banner** (offline, error) | `--surface-raised`, `--status-stale` or `--status-failed` edge with a word | offline, checking, back online, load error |
| **Counter / badge** | `--status-needs-you` text on `--surface-sunken`, at the icon's corner | 0 (none), n, "9+" |
| **Search, filter chips, sort** | `--surface-sunken`, `--border-line-strong`, chips as toggle buttons with counts in text | idle, active, no matches, count announced once |
| **Inline edit** (rename, replace, change scope) | `--surface-sunken`, `--border-line-strong`, count "n/40", `--status-failed` on error | idle, editing, saving, saved, failed (text kept), cancelled |
| **Undo window** | toast tokens | visible "Undo · 24s", expired |
| **Activity row** | `--text-soft`, `--type-small` | row, empty (`empty-ledger`) |
| **Owner-link note** | `--surface-raised`, `--border-line-strong`, non-modal | closed, open (Escape closes) |
| **Help entry** | `--surface-raised`, `--border-line` | collapsed, open |
| **Skeleton / loading** | `--surface-sunken` still rows, `--text-soft` | loading, still reading, stalled, timeout |

**Art.** The prototype's Dot, service icons, stamp and scenes are the generated art in `docs/vnext/prototype/art/`; the source and provenance are in `docs/vnext/prototype/art/PROVENANCE.md`. Round 1 adds `dot-peek`, `dot-tucked`, `dot-settled`, `icon-generic`, `scene-quiet` and `empty-ledger` (placed as in §4.0). Service icons are fixed squares (`--wv-icon-sm`, `--wv-icon-lg`) looked up by kind, with `icon-generic` as the fallback; `icon-local-weather` sits in Settings > Providers. Images use a transparent placeholder until the art resolves.

**Type.** Display: Young Serif (400); body: Atkinson Hyperlegible Next (400, 600 for labels, 700 for state words); system fallbacks (Georgia, Verdana) and **no external fonts in the prototype**. Roles: page and service titles `--wv-display-page`; section headings `--wv-display-section`; slip and card titles `--type-lead`; body `--type-body`; labels and chips `--type-label`; captions `--type-small`; MOCKUP label `--type-micro`.

**Icons.** Status glyphs are a single simple line set (check, alert triangle, clock, x in circle, question mark, dash), always beside their word. The house painted sticker icons may be used for nav in production at 20px or more beside their label; the prototype uses plain inline line glyphs as stand-ins. No emoji, no gradient.

## 7. Copy

Rule: **terse warmth** (see "Voice: terse warmth" after §1). Machine truth, then plain words, then (sometimes) a warm line. Warmth never creates a state, a deadline or certainty. As few words as possible, every honest fact kept. Avoid "provider", "capability", "endpoint" and "scope" in headings; gloss them when they must appear. State words stay exactly as `LANGUAGE.md` has them. These strings match `prototype/index.html`.

### 7.1 Status words and short labels
Healthy · Needs you · Stale · Unavailable · Unknown · Not configured · Working · Done · Failed. Live is shown only with a real checked time; a fact never checked reads Unknown. Freshness: "checked just now" (under 5s), "checked 24s ago", "checked 3m ago", "checked 2h ago", "checked 4d ago", "never checked"; one unit only. Absolute times carry their zone: "2:23 PM UTC" (or the device zone's abbreviation when Times is set to This device). Source: "From this device", "From its provider", "No source answered". Permissions: **Agent:** sees it · acts on it · no access. **Human:** sees it · edits the local copy · acts in {app} · no access.

### 7.2 Strings by screen

| Where | String |
|---|---|
| Top bar | "MOCKUP" · "Live" + "checked 24s ago" · "Live" + "none current" · "Paused" + "frozen at 24s" · "Paused · offline" · "Not checked yet" · "Simulate change" (assistive name: "Simulate change: back door locked"; after use "Already reported locked."; disabled with "Connect Front Door first") · "Add service" · "Disconnect Front Door" · disabled: "Disconnect" with "Connect something first" |
| Step cue | "1 of 3" · "Replay. Nothing changes." |
| W1 | "Hello, I'm Dot." / "A small counter for your services' facts." / "Connect the first one? Nothing here touches a network." / "Connect a service" / "Skip welcome" / "Dot's asleep." |
| W2 | "First, Media Shelf." / "Reference used only to read: {list}." / "Passed. Nothing changed." / "Connect Media Shelf" / "Next: Front Door" / "Skip welcome" |
| W3 | "Then Front Door." / "Connect Front Door" / "See the counter" / "Skip welcome" |
| First-receipt note | "One fact, traced." / "Media Shelf holds 1,284 items. Where from, who sees it, who acts." / "Every fact shows this." |
| H0 | "Quiet here." / "Connect something?" / "Nothing connected." |
| H1 status | "1 needs you · checked 24s ago" · "Nothing needs you · checked 24s ago" · "Last one done. Nothing needs you." |
| Receipt | "Where it came from" · "Source" · "Worlds" · "Agent / Human" · "Shared as {label}." · "Connected in first run · reference only, never the secret." · "Connected {time} · reference only, never the secret." · "Scoped to {n} capabilities" · "Unscoped" · "Updated now" |
| Fact row | "{label}" · "checked 12s ago" (ticks with the live feed) · value · state word |
| Kept out | "{n} fact kept out. Your choice." · "Kept out: {labels}." · "Change what's shown" · "Save" · "Cancel" |
| Search and filter | "Find a service" · "Needs you 2" · "Stale 1" · "3 of 12." · "No matches." · "Clear filter" · sort "Needs you first" / "Name" / "Recently checked" / "Newest" |
| Rename | "Name" · "12/40" · "Renamed to {name}." · "Kept {name}." |
| Many facts | "1 stale." · "Show all 40" · "No facts. {emptyReason}" · "changed 9m ago" · "oldest 8h" · "Live · none current" |
| Stale | fixture summary, then "No change seen since {time}." · button "Check now" |
| Unknown | "No current reading. Not guessing." |
| Unavailable (provider silent) | "Stopped answering. Last facts kept, with check times." |
| Unavailable (job rejected) | "Printer answered, so not silent." |
| Reference refused | "{Name} refused the reference. Last facts kept, with check times. Fix it in {Name}." · "Replace reference" · "Open Memory app" · "Checking now" |
| Test again | "Test again" · "Passed. 3 facts read. Nothing changed." · "Didn't go through." · "Next try in 30s." · "Check now" |
| Not configured | "Not set up. Open settings." |
| Frame | "Didn't load here." · "Still reading. 4s." · "Too slow." / "Cancelled." / "It won't show inside another page." · "Use the link, or try again." · "Try again" · "Open Home app" · "No Worlds credentials in here." |
| Needs you | "Needs you" · "New" · "Your call. Nothing acts on its own." · "Open Home app" · "Ask Project Home to review" · "Not available yet" · "Recently cleared" · "{Name}. Cleared 2:31 PM UTC. Home reported it." · "Nothing needs you." / "It'll show here." |
| Owner retry | "Not approvals. You retry these in the owning app." · "{Label}: tried {n} time(s). Last error: {lastError}." / "You retry in {App}. Worlds can't." |
| Handoff | "Approvals aren't connected." · "Nothing sent. Decide in the Home app instead." · "Once connected, this opens Project Home. It decides, not Worlds." |
| Proposal sample | "Sample. No real proposals." · "Proposed. Not active." · "Worlds can't run this, only show it. Decider: unknown. Agent can't." |
| Simulate | "Home says the back door's locked. Worlds locked nothing." · "Counter, Needs you and Agent facts all show it now." · "Last one done. Nothing needs you." |
| C1 | "Find a service" / "Looking only. No credential sent. Nothing changed." / "Available" / "Not connected · no reading" / "unverified" / "Auth: unknown" / "Already connected ×1" / "Add another of a kind you have." / "Couldn't look. Nothing changed. Try again." |
| C2 | "Credential reference" / "A name pointing to a secret kept elsewhere. Worlds stores the name only." / "May be used for" / "Used only to read: {list}." / "Scope only. What shows on the counter comes later." / pristine "Use the form ref://name." / dirty "Checked when you leave the field." / valid "Looks like a reference." / pending "Saving…" |
| C2 refused | "That looks like a secret. Cleared, not saved. Use a reference, like ref://notes-sync." · not a reference: "Not a reference. Use ref://name." · "Couldn't save. Nothing was changed." · Escape guard "Nothing saved yet. Escape again to leave." |
| C2 own secret | "That points at one of Worlds' own secrets. Can't use it here." |
| C3 | "Run safe test" / "Testing…" / "Passed. {n} facts read. Nothing changed." / failed "Didn't go through. Reference kept. Try again." / cause "{lastError}" / "tried 12s ago" / "try {n} of 3" / limit "Three tries. Check the reference in the owning app, then edit it." / mock "Simulate a failed test (mock)" |
| C4 | loading "Fetching facts…" / "Reading." / "Shaping facts." / "Reading 2 of 3 facts" / "Still reading. 4s." / "Stalled?" + owner link / empty "No facts yet. Nothing guessed." / "Separate facts. Capabilities verified." |
| C5 | "Choose what to show" / "Shown, and visible to agents: {list}." / "Keep at least one fact." |
| C6 | "Publish" / "Adds {Name} and its chosen facts to the counter." / "Carrying it over…" / "Connected" / "{Name} is here." / "Open {Name}" / "Add one more" / "Manage reference in Settings" / failed "Didn't publish. Nothing was added. Try again." |
| D1 | title "Disconnect {Name}?" / "{Name}'s {n} facts and app frame leave Worlds. The {App} app is untouched." / "Reference kept in Settings, unused." / "Disconnect" / "Keep service" / after: "{Name}'s gone from here. The app's fine. Reference kept." · "Undo · 24s" · "{Name} is back." · "Reconnect" · offline "Offline. Removed from Worlds." · failed "Couldn't remove that. Nothing was changed." |
| R1 | title "Remove {Name}'s reference?" / "Deletes the reference and what Worlds held for it. {Name} disconnects too, if connected. {App} is untouched." / "Worlds can't revoke the key. Rotate it in {App}." / "Remove reference" / "Keep reference" / after: "{Name}'s reference and connection removed. Key still active in {App}. Rotate it there." · "Open {App}" |
| Settings | "References only, never secrets." / "No references. Connecting adds one." / "Unscoped (older connection). Can be used for anything it offers." / "Held, unused" / "Narrow scope" / "Less motion. Same data." / "Undecided. This mockup keeps nothing." / "Couldn't save that. Nothing changed. Try again." |
| Memory | "No facts yet." / "Connect a service." / "Can't see it. {unknownReason} Needs the owning app to answer." / "Find a fact" / "No matches." |
| Activity | "Quiet so far." · "{time} UTC · {Name} · {what}. {who} reported it." · "This session only. Nothing is kept after you disconnect." · "Nothing held." |
| Help and reviewers | "What's a reference? A name for a secret kept elsewhere. Worlds keeps the name only." · "Start over" · "Clears this browser's mock. Nothing else." · "Stored in this browser: your settings and your services' names and references. Nothing else." |
| Offline | "Offline. Showing what was last known, with times." / "Offline · last checked 3m ago" / "Offline." (beside a disabled action) / "Back online. Checking." / "Checked just now." / "Away 4m. 1 thing changed." / "Couldn't load this." / "Nothing was changed." |

### 7.3 Announcements (one polite live region, one assertive)
Routine ticks are **not** announced. Messages inside 500ms are batched into one, and the polite region speaks at most one message every 2 seconds. Batched, polite messages only for: published ("Notes Sync connected."), disconnected (the D1 sentence), reference removed (the R1 sentence), a state change ("Media Shelf is now Stale."), renamed ("Renamed to {name}."), undone ("{Name} is back."), a new Needs you item (once), a failed save or removal, "Away 4m. 1 thing changed.", offline and back online, a result count ("3 of 12."), a failed test or failed publish (once, assertive, and not also written to the polite region: "Test failed." / "Didn't publish. Nothing was added. Try again."), live feed paused or resumed ("Paused. Freshness frozen." / "Live feed on."), and "Updated everywhere. Home reported the back door locked. Worlds locked nothing."

## 8. Motion and accessibility

### 8.1 Motion

One curve, `--wv-ease`. Motion confirms a change that has already happened.

| What moves | Why | Normal | Reduced motion |
|---|---|---|---|
| State word on a slip, chip and receipt | confirm a change | cross-fade 150ms (120ms phone) | instant swap, opacity only |
| Receipt stations and Memory rows | show the journey settling | tick at Source, Worlds, Agent / Human, 60ms apart | all ticked at once, no stagger |
| Dot nod | "I noticed" beside "Updated now" | 200ms, once | no nod and no pose swap; "Updated now" stays 3s |
| "Updated now" | confirm | fades in and out at `--wv-dur-state` | instant |
| Dot's parcel | publishing, welcome connections | travels 400ms desktop, 300ms phone | parcel appears at the counter, no travel |
| Connected stamp | the proud moment | scales in (1.35 to 1) and lands tilted, 280ms | appears in place |
| Undo parcel | the service comes back | `dot-parcel` mirrored, 400ms desktop, 300ms phone | appears at the counter |
| Slip hover and select | affordance | lifts about 2px; scale only on buttons, 1.03, off on touch | no transform |
| Dialog and sheet | context | the dialog fades and lifts 1rem; the phone sheet rises from the bottom edge; 200ms | none |
| Toast | confirm | fades and rises 200ms | instant |
| Step change in Connect | continuity | content fades 150ms | instant |
| Plain feed tick | freshness | only the age number changes (tabular figures, no jitter) | same |

Respect the OS reduced-motion setting unconditionally; Settings can additionally force "Reduce always". Both go through one `motionOK()`; no transform survives, including button `:active` nudges and the brief lane flash before a stamp. Reduced motion removes animation, never data. Nothing flashes. No parallax. Dot's idle pose is still.

### 8.2 Keyboard map
- **No single-key shortcuts** (avoids accidental triggers and conflicts). Everything is reached with Tab, Shift+Tab, Enter, Space, arrow keys inside radio groups and selects, and Escape.
- **Skip link** "Skip to Worlds" is first; it moves focus to `main`.
- **Tab order** equals reading order: skip link; top bar controls (`#live-toggle`, `#simulate-change`, `#add-service`, `#disconnect`); nav (rail or tab bar; on phone the header Settings button comes before main); main content in the order in §4; dialogs trap focus and return it.
- **Slips:** each is a button with `aria-pressed`; Enter or Space selects. **Fact rows:** buttons with `aria-pressed`. **Step list:** not focusable except the Back / Next buttons.
- **Escape** closes dialogs, sheets, the owner-link note and the handoff panel and returns focus to the invoking control. Escape on Connect asks nothing when nothing is saved; if something was typed or ticked the first Escape says so and the second leaves. Escape in a rename or replace field cancels it and returns focus to its button. Browser Back closes an open dialog or sheet before it leaves the screen.
- **"Skip to Worlds"** focuses `main` without changing the route; on phone a second skip link, "Skip to navigation", follows it.
- **Repaints never take focus.** A repaint is held while a text field or select has focus; every control carries a stable key so focus is restored to it, and when its element is gone focus goes to the nearest preceding heading. A confirm button ignores key-repeat and a second activation.
- Disabled-with-reason controls use `aria-disabled="true"` so they stay focusable and readable, never the `disabled` attribute that drops them from the tab order (permission `none`, disabled `#disconnect`, `#simulate-change` with no Front Door, the last chosen fact, the history option, the test after three tries, any action while offline).
- **Focus visible** everywhere: `--focus-ring`, thick, offset, from tokens in every theme. Focus is never hidden behind the top bar or the tab bar (scroll margin set).
- **Focus moves** to the new heading on every push, step change and destination change (`tabindex="-1"`), and returns to the invoking control on Back or close.

### 8.3 Screen-reader structure
- Landmarks: `header` (banner), one exposed `nav` ("Worlds sections"; the rail or the tab bar, whichever is shown), `main`, one polite `role="status"` region and one assertive `role="alert"` region, each created once and never re-rendered. The document title follows the route.
- One `h1` per screen (the screen's name); `h2` per section; slips list is a `ul` of buttons labelled with name and state ("Front Door, Needs you, checked 24s ago, selected"), the age written once at render and the ticking text `aria-hidden`, the reason tied by `aria-describedby`; selecting on desktop announces "Selected Front Door."; the receipt is a section with `h3` per station.
- State is always text. Dot is `aria-hidden` unless a sentence names it; the stamp reads "Connected".
- The step list is an `ol` with `aria-current="step"`; a phone "Step 3 of 6 · Test" line is real text.
- Forms: visible labels, errors tied with `aria-describedby`, `aria-invalid`, and the refusal never repeats the secret.
- Tables are not used for layout; Memory rows are articles under service headings.

### 8.4 Targets, reflow, text
Every interactive target is at least 44px (`--wv-target-min`) with 8px (`--space-sm`) gaps; nothing under `--type-micro` except the MOCKUP label; long values wrap (`overflow-wrap`), never truncate; browser zoom and text scaling are never blocked, and at 200% the page reflows without sideways scroll. The one place text is cut is the top bar's `#disconnect` label (20 characters, ellipsis), with the full name in its accessible name and `title`; every other long name wraps. At 320px width and 200% text nothing clips or hides under a sticky bar (their heights are measured).

### 8.5 Contrast in all four house modes
Measured from `tokens.css` (WCAG ratios; text needs 4.5:1, non-text and borders 3:1). `base` = `--surface-base`, `raised` = `--surface-raised`, `sunken` = `--surface-sunken`.

| Pair | Dark | Light | High contrast | Low stimulation |
|---|---|---|---|---|
| `--text-primary` on base / raised / sunken | 13.8 / 12.1 / 15.1 | 14.4 / 15.5 / 12.6 | 18.2 / 15.5 / 19.1 | 12.8 / 11.8 / 14.1 |
| `--text-soft` on base / raised / sunken | 10.2 / 8.9 / 11.2 | 7.2 / 7.8 / 6.3 | 16.2 / 13.8 / 17.0 | 9.0 / 8.3 / 9.9 |
| `--action-on-primary` on `--action-primary` | 11.3 | 7.6 | 15.6 | 8.7 |
| `--action-primary` on raised (as link or border) | 9.9 | 7.6 | 13.3 | 7.3 |
| `--focus-ring` on base / raised / sunken | 13.3 / 11.7 / 14.6 | 14.4 / 15.5 / 12.6 | 18.2 / 15.5 / 19.1 | 11.3 / 10.4 / 12.4 |
| `--border-line` on base / raised | 3.9 / 3.4 | 3.7 / 4.0 | 18.2 / 15.5 | 3.9 / 3.6 |
| `--border-line-strong` on raised / sunken | 5.4 / 6.8 | 7.8 / 6.3 | 15.5 / 19.1 | 5.1 / 6.1 |
| `--status-healthy` on raised / sunken | 10.1 / 12.7 | 6.1 / 4.95 | 13.4 / 16.4 | 8.9 / 10.6 |
| `--status-needs_attention` and `--status-stale` on raised / sunken | 9.5 / 11.9 | 6.6 / 5.4 | 12.0 / 14.8 | 8.6 / 10.2 (needs-you) · 7.3 / 8.6 (stale) |
| `--status-unavailable` on raised / sunken | 7.7 / 9.6 | 6.9 / 5.6 | 10.5 / 13.0 | 7.2 / 8.5 |
| `--status-unknown` and `--status-not_configured` on raised / sunken | 7.7 / 9.7 | 7.8 / 6.3 | 13.8 / 17.0 | 7.3 / 8.6 |

Every pair passes. Two things the numbers cannot do, so the design handles them in words and shapes: (1) in Dark, Light and High contrast "Needs you" and "Stale" share one colour, and in Low stimulation "Stale", "Unknown" and "Not configured" share one; the word and the glyph are what tell them apart. (2) In Light the Dot's apricot shell and mint body are dark tones, so Dot's ink (`--surface-base`) is light; it must be checked once rendered. The `--border-line` values pass 3:1 but are the lowest ratios in the system; interactive controls therefore use `--border-line-strong`. These are token measurements, not a check of the built prototype (Q9). The build pass also measures what sits outside the token pairs: the needs-you badge (`--surface-base` on `--status-needs-you`), Dot and the painted art on each surface, the toast border against base in Light, and how `aria-disabled` reads in High contrast; it adds `forced-colors` rules (outlines and real borders survive, shadows do not, so the add pill and the toast carry borders) and runs an automated pass plus a screen-reader pass (NVDA, VoiceOver macOS and iOS, TalkBack).

## 9. Reactivity

**One store keyed by fact id** feeds the slips, the service surface, the receipt, Memory, Settings, Activity, the attention count and the top bar. A change re-renders only the slices that show it (a tick repaints ages only; a state change repaints the three or four places it appears), so a repaint never takes the person's focus, caret, selection or scroll. Ages are always recomputed from `checkedAt`, never taken from the fixture's `ageSeconds`. The components that do this are in "Reactive components".

- **Mock clock** starts at the fixture's `generatedAt` (2026-10-13T14:24:26Z) and runs in real time from page load, from `performance.now()` (it doesn't drift or stop in a hidden tab, and the welcome doesn't freeze it), so first paint reads Front Door "checked 24s ago" and Media Shelf "checked 28s ago". No invented numbers. Returning to a hidden tab applies every scripted event that passed, in order, then renders once. Absolute times print with their zone.
- **Persistence.** The person's own settings and services (theme, motion, cadence, times, welcome state, each instance's name, reference, scope, kept-out facts and connected time, selection, filter, sort) are saved in this browser under one versioned key. Never saved: anything typed before it passes the reference check, any refused value, the clock, scripted state (the proof path restarts on load), the Activity log, the undo snapshot. A corrupt, old or blocked store is dropped quietly and the mock starts clean. "Start over" clears it.
- **Tick:** every 5s by default (Settings: 10s or 30s; changing it restarts the cadence from now). A tick updates every age everywhere and nothing else moves.
- **Re-check rule (per fact, not per service).** Any fact whose state is Live re-checks every 30s while the feed is on. A re-check changes `checkedAt` and `observedAt`, never the value. A missed re-check is retried at 2s and 4s. Facts that are Needs you, Unavailable, Unknown, Not configured or already Stale don't re-check; their ages grow and their words stay.
- **Silence rule (the prototype's stand-in for Q6).** A Live fact with no successful check for 3× the re-check interval (90s) shows **Stale**; for 5× (150s) **Unknown**. It applies to every Live fact, so a fourth service needs no new line, and it stops while the feed is paused or offline.
- **Scripted missed re-check, the proof path.** Each session arms **two** scripted misses, both labelled "simulated", which are this rule at a short fuse: one on Media Shelf's first live fact, and one on the **first live fact published through Connect** (for Notes Sync, "Local notes waiting to upload"). 90s after the fact becomes live (the welcome counts as first load for Media Shelf; Publish for the Connect one), it misses a re-check and becomes **Stale (simulated)**, keeping its last value as a labelled "last known". "Check now" restores it to Live. If it is left, **60s later** it becomes **Unknown (simulated)**, still showing the last value only as "last known". Each fact is scripted once per session. A service's own state word keeps following its fixture state; the fact carries its own state (facts are never merged) and that state is visible on the slip, the header and the receipt (ChangeRipple settles all of them, including on a scripted change). Two facts changing in the same second are reported in one message.
- **Retry with backoff (Unavailable services only).** Worlds re-attempts a read of an Unavailable service at 15s, 30s, 60s, 120s, then every 5 minutes, ±20% jitter, and shows "Next try in 30s." An attempt is not a reading: it never changes a value or `checkedAt`. "Check now" resets the ladder. Owner retries (`probe-provider`, `retry-last-job`) stay links to the owning app; Worlds has no retry button for them. Needs you services wait on a person and aren't retried.
- **`#simulate-change`:** the Home app reports the back door locked (fixture `crossViewExample`, `lock-back-door`). In one frame: `frontdoor.back-door` reads "locked", Front Door becomes Healthy, the attention count goes 1 → 0 in the status line, the Needs you badge, the slip, the service header and Memory. The change comes **from the owning app**, not from Worlds: "The Home app reported the back door locked. Worlds locked nothing." stays visible with "Open Home app", and a note names the places that moved. Worlds never shows `lock-back-door` as a pending proposal. The button is `aria-disabled` (reason visible) with no Front Door connected, and after use. A reviewer control reverses it.
- **Optimistic then settled:** Publish, Disconnect, Revoke, Replace, Rename and Settings saves show their result in the same frame, then settle visibly and name what changed (OptimisticAction). A failed one rolls back to what the screen was, keeps the person's text, and says why once. Disconnect offers a 30-second Undo.
- **Pause and resume:** `#live-toggle` (`aria-pressed`, on by default) freezes the clock, ticks, re-checks, backoff and the stale event; data, actions (including in-flight tests and publishes) and `#simulate-change` still work. Resume continues from the frozen time and, after a pause over 60s, re-checks every Live fact once. It reads "Live" or "Paused" with "checked 24s ago" or "frozen at 24s" beside it. `#settings-live` is the same state and always agrees.
- **Offline:** the browser event (or the reviewer control) pauses the feed and freezes ages; states keep their own words and Live facts read "Offline · last checked 3m ago"; the person's live or pause choice is remembered separately; on return one re-check of every Live fact runs ("Back online. Checking." then "Checked just now.").
- **Announcements:** routine ticks are silent; meaningful changes are batched into one polite message, at most one every 2s (§7.3). A failed test or publish uses the one assertive region.
- **Words for the feed:** every feed-driven change carries the word "simulated" where it appears, so nothing reads as a real reading. A card shows the word in full once (the receipt); other places show a small "sim" pill with the full word in `title` and hidden text. The mock clock note is in About.

## 10. Trust and boundaries

Sol's six conditions are pre-prototype gates (Project Home decision 145: "Approve the boundaries; Sol's six conditions become pre-prototype gates"). This design makes each visible. Items marked *gate check* are things the prototype must show before it is shown to anyone as proof.

| # | Condition | Where it appears in the UI | Gate check |
|---|---|---|---|
| 1 | **Project Home approval is fail-closed.** Never shown as working; an approval is a link or handoff that can say "not available yet". | §4.7 N1 and N2: "Ask Project Home to review" is labelled "Not available yet"; the panel says "Approvals aren't connected yet" and "nothing was sent". No "sent", "pending", "approved", spinner or recorded-handoff receipt anywhere, and no pending-approval line in any dialog (none can exist). Unknown connectivity renders as not available. **There is no Settings row, mock control or other UI path to a "connected" state.** A reviewer-only flag, if ever needed, is a build-time constant in the prototype file, off in the shipped mock and unreachable from the UI. | Click the handoff in the default build and confirm nothing reads as done; search Settings, About and For reviewers for any control touching approvals (there must be none). |
| 2 | **Proposed actions are inert.** Shown as proposals; never executable from Worlds. | §4.8: the one sample proposal reads "Proposed. Not active." with "Agent can't do this." There is no Run, Do it or Approve control on a proposal, and the fixture-true owner retries are links to the owning app, not buttons. `#simulate-change` models an *owner-originated* change, not execution. | Search every screen for a control that executes a proposal or a retry; there must be none. |
| 3 | **Scoped auth before any network call; legacy unscoped labelled "unscoped".** | §4.4 C2: the **send-scope** list (capabilities) and its sentence "Used only to read: {list}" must be satisfied before Test can run; Discover says no reference has been used. C5's publish selection is a separate, differently named list. Settings > Credential references and the receipt's Worlds station show "Scoped to {n} capabilities" or "Unscoped" with "Narrow scope" (which opens Connect at Reference) for unscoped ones. The welcome's connections are scoped. | Test cannot run with no scope; the C2 and C5 lists are visibly different; Unscoped is visible in Settings, Memory and the receipt after the For reviewers control. |
| 4-5 | **Contract fixes** (completed in the Connect contract, draft PR #329). | Not a UI element. The UI follows the contract as it stands: six verbs, `disconnect` keeps the reference (`credentials_retained`) and `revoke` is the only path that deletes it (R1), `external_state_untouched` is said plainly. | The spec and prototype cite only fields the contract has. |
| 6 | **The read-only path is proven first: keyboard, mobile, stale and unknown.** | Everything in this design before Needs you is read-only. The acceptance path (below) is run first, on a service the person actually connected. | See "Read-only path acceptance". |

**Read-only path acceptance (condition 6), the proof path.** All of this must pass before proposals, approval or any later work is built on top of it:
1. Empty counter → welcome (skip works, and so does connecting two) → Discover (no readings shown) → Reference (a secret refused and cleared; a capability scope chosen) → Test (a failure, then a pass) → Preview → Choose → Publish → Connected.
2. The **published** service's live fact goes **Stale** (word, last-known value, time), then **Unknown** (words, no number), by the scripted rule in §9 with no reviewer waiting beyond the 90s and 60s timers (or the For reviewers control "Make Media Shelf stale now" for the seeded service). The change is visible on the slip, the header and the receipt even when the service word is Unavailable, and it settles and nods.
3. Follow a link out to the owning app (Open Memory app).
4. **Revoke** (what goes, what stays, the provider's key still active), and **Disconnect** (what goes, what stays, the reference kept), then the counter is empty and **Worlds still works** (Memory, Settings, Connect).
5. All of it by **keyboard alone** (visible focus, focus returns, Escape closes, the skip link works), and on a **390px phone** (no sideways scroll, 44px targets, one bottom strip) and at 320px and 200% text.
6. In all four themes, and with reduced motion on.

**Other boundaries kept visible**
- **Worlds owns meaning; providers own mechanics.** Worlds shows and links; it never mints authority. A governed action goes to the owning system (Project Home for approvals, the service's own app otherwise). "Worlds locked nothing." is said in words.
- **No secret ever.** Only references are accepted, and a refused secret is cleared and never echoed, stored, logged or kept in the Activity log, in Connect, in Settings Replace and on paste.
- **Disconnect and revoke are honest and different.** Disconnect keeps the reference. Revoke deletes it and says Worlds can't revoke the service's own key.
- **Nothing is shown as a real reading.** MOCKUP label on every screen; "simulated" on every feed-driven change; synthetic data only; Discover shows no reading before one exists.
- **The frame gets no Worlds credentials.**

## 11. What the prototype must show (pointer to deliverable 2)

The prototype implements this spec as one self-contained HTML file with no network, using the house tokens only. Checker ids: `#skip-welcome` (every welcome beat), `#add-service`, `#disconnect` (visible on the first screen; confirm button labelled "Disconnect"), `#simulate-change`, `#live-toggle` (same id; its text is "Live" or "Paused" with `aria-pressed`, and the age text sits in an adjacent node: a checker reading the toggle's text should read it and its neighbour), plus `#settings-live` and `#disconnect-{service-id}` in Settings (the instance id; the first Media Shelf stays `media-shelf`). Visible MOCKUP label. Desktop, tablet and phone layouts. It must demonstrate the proof path in §10 and the failure path (a failed test, a refused secret, a refused frame, a failed publish, a failed save, offline, a fail-closed handoff), and every item in "Refinement round 1: checklist". A one-file page test (no network) checks: no length literal in padding, margin or gap outside `:root`; no inline style with a length; relative-age boundaries (0, 4, 5, 59, 60, 3599, 3600, 86399, 86400 seconds); a refused secret never reaches the DOM or storage; one polite and one assertive region; every action button has a stable key; the proof path end to end including offline, reload and 24 services; and a table of hostile names (markup, quotes, right-to-left override, zero-width, joined emoji) shown as text on every screen. A browser pass (keyboard only, 390px and 320px, 200% text, four themes, reduced motion by OS and by "Reduce always", NVDA and VoiceOver) is recorded in the Q9 row. The shipped mock has **no UI path** to a connected approval state.

## 12. Open questions and UNKNOWNs

**Questions for Rylee or the team**
- **Q1.** Does Connect truly belong at the Explore door? The Connect contract is Platform/Capability; only its screen is Experience. If Explore later means Hive Works exploration, Connect could instead be a Home action with no door of its own.
- **Q3.** Disconnect keeps the reference (as the contract does) and revoke deletes it. Confirm the two-step shape.
- **Q5.** Status label: this design uses LANGUAGE.md's "Needs you" where V2 showed the fixture's "Needs a human". Confirm.
- **Q7.** "Human can" and "Agent can" are kept from V2; plain-word alternatives ("You can") were rejected earlier. Confirm.
- **Q8.** Should the `--wv-*` handles (target floor, hairlines, durations, rail width, the two display sizes) be promoted into house tokens, given the house rule that structural roles live in tokens and the target floor lives with Play-Nice?
- **Q10.** Does a service publish to a named board? The contract's `PublishSelection.board` must be an existing board; Worlds shows none today (one board, no control). Confirm, or give C6 a line for it.
- (Q2, how many services the first run offers, is settled in this spec: the welcome connects two, one at a time, and skip connects none.)
- (Settled by Claude in round 1, open to Rylee's veto: the curious Dot beside Stale and the goodbye Dot stay; the stamp takes 280ms; the live toggle keeps its id with the age beside it; phone Settings is pushed screens; the Needs you count is decisions; undo after disconnect is 30 seconds of mock time.)

**UNKNOWN**
- **Q4.** The real sandbox rules and browser support for embedded apps.
- **Production Connect API** and credential-reference grammar. The contract's references look like `env:`, `vault:` or `file:`; the prototype uses `ref://name` from V2. These must be aligned before a real build.
- **Authority.** The fixture has no authority field, so whether Front Door or any service is governed by Project Home, and so whether "Ask Project Home to review" is ever the right route, is UNKNOWN. The sample proposal shows "Decided by: not known yet".
- **Project Home approval verification.** The contract notes the verify step has no implementation, so the path is fail-closed end to end. This design assumes "not available yet" until proven otherwise.
- **Q6.** What makes a service Stale in production (probably each read's time-to-live) versus the scripted event and the 3×/5× silence rule used here.
- **Live feed transport and cadence** in production.
- **Disconnect history policy:** whether anything is kept. The disabled "Keep history after disconnect" stays until decided. The 30-second Undo and the session-only Activity log are in-memory and don't decide it.
- **Whether a fixture's facts map one-to-one to the contract's capabilities** (the send-scope list in C2 assumes a capability list per service; the prototype derives it from the fixture's facts for the proof-path services).
- **Q9.** Contrast, focus, reflow, screen-reader order and the checker are **not verified** by this document. Contrast numbers come from the tokens; they must be re-measured on the built prototype at desktop, tablet and phone sizes, in all four themes.
- **Dot in Light mode** (see §8.5) and the exact shell and body colours; the new art (`dot-peek`, `dot-tucked`, `dot-settled`, `scene-quiet`, `empty-ledger`, `icon-generic`) is unmeasured on all four surfaces.

## Appendix A: Critique fixes

| Gap | Fix | Where |
|---|---|---|
| **1. Type rule flattened the display voice** | Accepted. Change #6 now says what is true: the house leaves headings past `h1` to the product, composed from its tokens; V2's *source* was loose, its design asked for a composed handle. Added `--wv-display-page` (2.5rem) and `--wv-display-section` (1.85rem) as named local handles; page, service and welcome titles use them. No `clamp()`. | §1 item 4, §2 change 6, §6 |
| **2. Welcome did not earn the counter; unearned provenance** | Took the "earn the two services" route. W1 is V2's single broad card with a sleeping Dot and one button; W2 and W3 connect Media Shelf and Front Door with the parcel and stamp each time; skip connects none and the counter is then empty. "Connected in first run" is now true of something shown. The fact-journey became a dismissible note after the first connection. Q2 is removed. | §2 change 9, §4.1, §4.3 |
| **3. Feeling specified for one screen, audited for none; phone tabs; Memory; tablet labels** | Added a per-screen Carries table (§4.0) and gave Memory, Settings and Connect a named gesture (Dot resting in the header, the 60ms settle on Memory rows, the dashed empty well). Phone bar is four doors; Settings is a header button. Memory is a trail with owner links and "what would help" on Unknown rows. Tablet rail labels are always visible, with a keyboard tooltip. | §3, §4.0, §4.12, §5.2, §5.3 |
| **4. Inert proposals built on invented fixture data** | Removed the fixture-labelled proposals. `probe-provider` and `retry-last-job` are shown as what they are (owner retries by a person, link only). `lock-back-door` appears only in its applied form. One proposal sample is drawn from the contract's `ActionProposal` shape, marked "Sample. The fixture has no proposals.", with "Decided by: not known yet" bound to `authority` (UNKNOWN). | §4.7, §4.8, §10 |
| **5. Proof path could not be walked** | Re-checks are a per-fact rule, not a table of constants. Each session arms a scripted missed re-check on Media Shelf's first live fact and on the first live fact published through Connect, with the 60s escalation to Unknown and "Check now". Discover now shows "Not connected · no reading", unverified capabilities and "Auth: unknown", never a state word. Acceptance step 2 runs on the published service. Because Notes Sync starts Unavailable, the fact (not the service word) carries Stale and Unknown, consistent with "facts are never merged". | §4.4, §9, §10 |
| **6. Scope screen was the publish selector** | Named two fields once: C2 is the credential's **send scope** over capabilities (contract `CredentialReference.scope`); C5 is the **publish selection** over facts. Different sentences, different words. Settings and the receipt say "capabilities". "Narrow scope" opens Connect at Reference, pre-filled (Discover first for an older connection with no stored list). | §4.4, §4.13, §10 |
| **7. A toggle could switch fail-closed approvals to connected** | Removed the Settings mock control. "Link ready" is a design note only; no UI path reaches it; any reviewer flag is a build-time constant, off and unreachable. The remaining mock controls only produce failure or edge states. | §4.7, §4.13, §10, §11 |
| **8a. Studio Printer wrong cause** | One Unavailable line per cause; Studio Printer uses the fixture's own sentence ("reachable but rejected the job"). | §4.9 |
| **8b. Stale line erased Nightly Backup's reason** | The fixture summary is always shown; the "Nothing has changed since…" line goes under it, and stands alone only where no fixture reason exists (scripted staleness). | §4.3, §4.9 |
| **8c. Unrenderable pending-approval line** | Deleted from the disconnect dialog; the gate says no pending-approval line exists in any dialog. | §4.10, §10 |
| **8d. Revoke had no screen** | Added R1 with its own three-part consequence list (what goes, what stays, the provider's key still active). Disconnect keeps the reference (`credentials_retained`) and the "Also remove the reference" tick is gone; revoke is the only path that deletes it. Acceptance step 4 walks both. | §2 change 4, §4.10, §4.11, §7.2 |

## Appendix B: decisions in force (quoted)

- 2026-10-13 Rylee: "Yeah. V2 is the only one that passed. Can we now feed that back in with all the field guide info and everything to generate a full design?"
- 2026-10-13 Rylee: "comprehensive but also keep the original feeling." Clarified: protect the feel, the look, the whimsy and the love, NOT the copy; copy may be rewritten for clarity (LANGUAGE.md).
- 2026-10-13 Rylee: "Go with concept 5 from here. Bring it into our design language and have it make a few variations based on the overall flow please"
- 2026-10-13 Rylee: "the more real application with whimsy and warmth laced in but make sure they have both desktop and mobile and are reactive <3"
- 2026-10-13 Rylee, Project Home decision 145: "Approve the boundaries; Sol's six conditions become pre-prototype gates" (the Connect contract, draft PR #329).
- 2026-10-12 Rylee: "Field Guide as base" (the World Tree Field Guide is the base of the shared design system; Mulberry & Mint).
- 2026-10-13 Rylee: "I love this. Let's send back for one round of refinement and to get every additional piece down and all the reactive elements we might need. Please. I'd like this to be a little robust and polished along with our whimsical snail" (see "Refinement round 1: checklist").
- 2026-10-13 Claude's calls on the audits' open questions, keeping the protected feeling: keep Dot curious beside Stale and Dot's goodbye after disconnect; the stamp may take 280ms; the live toggle keeps its id `#live-toggle` (its age text may move beside it); phone Settings may become pushed screens; "needs you" counts decisions; in-session undo after disconnect lasts 30 seconds with a visible "Undo" (mock time), and the "keep history after disconnect" decision stays open.

None of these is contradicted by this document. Where it departs from V2's wording (§2), it does so inside the "copy may be rewritten" clarification or to honour decision 145.
