# Critique — "Worlds vNext: the full design (MOCKUP spec)"

Reviewed against `docs/vnext/full-design-brief.md`, `docs/vnext/v2/`, `docs/vnext/concept5/`,
`docs/vnext/field-guide/`, `docs/vnext/house/`, `docs/vnext/connect/connect-contract.md`,
`docs/vnext/concept-brief-v2.md`, `docs/vnext/concept-brief-v3.md` and
`docs/vnext/fixture/fixture.json`. Eight gaps, most important first. Nothing here says a decision
in force is wrong; the decisions quoted in the brief are treated as binding, and every fix below
stays inside them.

What already holds up, so the gaps read as "not yet" rather than "wrong": §1 is written first, as
the brief asked, with thirteen concrete items and a source selector for each — that is the right
instrument. The IA table maps the four Field Guide doors honestly and says where Settings sits
outside the skeleton. The fail-closed approval work is the strongest part of the document. I
re-measured §8.5's contrast table against `house/tokens.css` in all four modes: the numbers are
right (dark `--text-soft` on raised 8.94, light `--border-line` on sunken 3.21, the lowest status
pair light healthy-on-sunken 4.95 — everything clears its floor). Every token name used in §6
exists in `tokens.css`, including the `--wv-*` aliasing pattern the house sanctions
(`house/DESIGN.md:96-111`). Nothing in the gaps below is a token or contrast problem.

---

## Gap 1 — the type rule the spec calls a correction would flatten the display voice it promises to protect

**What is wrong.** Change #6 says "Heading sizes come only from `--type-h1`, `--type-lead`,
`--type-body` plus weight and spacing", on the grounds that "V2's DESIGN §9 says so; V2's source
used `calc()` multiples of `--type-h1`, which breaks that rule", and §6 repeats it: "The welcome
heading uses `--type-h1` with more space and weight, not a bigger literal size."

The house says the opposite of the first half. `house/DESIGN.md:111`: "A heading ladder past `h1`
is **a product's typographic decision, composed from these**." A product-local handle that reads a
shared token larger is the sanctioned aliasing mechanism (`house/DESIGN.md:95`), not a violation.
V2's `DESIGN.md` §9 says the same thing — "compose larger welcome emphasis only from `--type-h1`
plus spacing and weight" — so the spec's claim that V2's design forbade what its source did is
mis-cited. Only the source was loose: `v2/index.html:27` sets `h1` at
`calc(var(--type-h1) * 1.65)` (2.475rem) and `h2` at `1.25×`.

Taken literally, the spec puts the page title at `--type-h1` = 1.5rem (`house/tokens.css:39`)
against `--type-body` = 1rem — a 1.5:1 step — where the built V2 the brief protects runs at 2.48rem
and 1.88rem, a 2.5:1 step.

**Why it matters.** §1 item 4 of the spec says the serif gives the counter "a printed,
hand-labelled air". Most of that air is the size jump between the serif display and the reading
face; at 1.5rem the Young Serif headings are barely larger than body copy and the whole product
reads as documentation in Georgia. And because this rule binds every screen, it is the single
largest generator of "generic app screens" in the document — the exact outcome the brief's
§1-review-criterion paragraph forbids.

**Concrete fix.** Keep the substance (no un-tokened literals, no `clamp()`) and express it the way
the house does. In §6 declare two Worlds-local display handles — `--wv-display-page` (2.5rem) and
`--wv-display-section` (1.85rem) — recorded as `the product's typographic decision past h1,
composed from --type-h1 per house/DESIGN.md:111`, next to the existing `--wv-*` block; use them
for the page title, the service title and the welcome heading; keep `--type-lead` and `--type-body`
for everything else. Then correct change #6 to say what is actually true: V2's **source** used
untokened `calc()` multiples where its design asked for a composed handle.

---

## Gap 2 — the welcome no longer earns the counter, and two services arrive that were never connected

**What is wrong.** §1 item 12 promises "V2 opens on a single broad welcome card with a sleeping
Dot, one invitation and one button", and calls it protected. §4.1 builds three beats instead: W1 is
an **awake** Dot with "Next", W2 a static fact diagram with "Next", and W3 is the only beat with a
"Connect a service" button. Since `#skip-welcome` is on every beat and the brief protects the
welcome's pacing as "unhurried, skippable, one thing at a time", the commonest first-run path is:
awake Dot, two sentences, skip — the broad welcome card never appears and Dot never carries
anything. V2's built welcome (`v2/index.html:76`) is the opposite: one broad raised card, one
invitation, "Connect a service", `dot(true)` carrying the first slip.

Then §4.3 asserts an "initial settled set" of Media Shelf and Front Door that W1–W3 never connect
and that C1 already lists under "Already at the counter" — while their receipt provenance row
claims "Connected during first run · reference held, never the secret" (§4.5, §7.2). The design
asserts a provenance event it never shows. §12's Q2 is still open ("should the first run … offer
none (as W3 does now)?") while §4.3 already depends on the answer.

**Why it matters.** "Dot carrying the first service slip" is V2's named onboarding signature
(`v2/DESIGN.md` §10) and the brief protects the look of both concepts. The spec moves the parcel
behind a Next button on the last beat, where skipping is advertised. And the provenance row is the
daily receipt's warmth — the line that carries V2's welcome promise into every later session — so
it has to be true of something the person watched happen.

**Concrete fix.** Make beat 1 the V2 card: broad raised card in a sunken well, **sleeping** Dot,
the two plain sentences, one primary "Connect a service", "Skip welcome". Then resolve Q2 inside
the text, one way or the other:
- **Earn the two services** (V2's route): the welcome runs both connections with honest
  first-service / second-service progress and the parcel each time, landing on the settled counter
  — §4.3's settled set is then earned and "Connected during first run" is true; or
- **Offer none**: delete the settled set, make §4.3 start from whatever the person actually
  connected, and change the seeded services' provenance row to "Connected {when}" so no first-run
  claim is made about an unshown event.

Either way, delete Q2 and keep the fact-journey beat and the six-step promise as depth reached
after the first connection, not as the front door.

---

## Gap 3 — the protected feeling is specified for one screen and audited for none

**What is wrong.** §1 sets the rule: "Each new screen in §4 must name which of items 1-13 it
carries." The document then fails its own rule. C1 carries "5", C2 carries "11", C5 carries "11";
M1, T1–T5 and X1 name no carried items at all; N1 and D1 name only their absence ("No Dot on item
cards, no flourish"). §1 item 6 places Dot "beside the counter's freshness line", and a freshness
line exists only on Home's slips and the service surface — so Needs You, Memory, Settings and
Connect have no Dot and no counter motif. That is the failure V2's own critique already named and
fixed ("Nothing on a working screen moves or warms", `v2/CRITIQUE.md:210`).

Two smaller things ride with it. Phone gets five equal bottom tabs (§5.3) where the Field Guide
asks to "Preserve the shared four doors (Home, Explore, Needs You, Guide)"
(`field-guide/world-tree-DESIGN-REFERENCE.md:251`) and §3 itself calls Settings "not a door; a
utility" — five equal tabs is the shape of every generic app and the only shape a phone user ever
sees. And Memory, mapped to Guide ("understanding and continuity", "leave a followable path",
`DESIGN-REFERENCE.md:30`), is specified as a flat filtered inventory with no path: no owner link
per service, and no "what observation would resolve this" on Unknown rows, which is the Guide
door's own defined behaviour (`DESIGN-REFERENCE.md:193`).

**Why it matters.** Two of the three most-visited destinations and the whole of Connect read as
lists and forms. The whimsy stays exactly where a daily-use product does not have it: the first
five minutes.

**Concrete fix.** Three additions, each cheap and none a gate:
- **A per-screen Carries table** in §4 replacing the per-step notes, so the rule is auditable, and
  give every working destination at least one named moment from §1: Dot at rest on the Memory and
  Settings headers; the 60ms receipt settle on Memory rows when a change lands; the counter's
  dashed empty well reused as Memory's empty state instead of a generic empty card.
- **Four phone tabs, not five** — the four doors — with Settings reached from the page header of
  any screen. Keep the five-label phone bar out and the skeleton stays visible.
- **Memory becomes a trail**: one owner link per service heading, and on Unknown rows the line
  "Worlds can't see it. {fixture unknownReason} What would help: the local app answering again."

**And on tablet** (§5.2): the rail's labels show "on focus and hover". Hover does not exist on a
768px tablet, so a touch tablet user gets bare icons; Concept 5 kept a tooltip beside the focus
label (`concept5/DESIGN.md:73`). Restore the tooltip, or keep text visible until first use.

---

## Gap 4 — the inert proposals are invented data, built on fixture fields that are not proposals

**What is wrong.** §4.8 says "Fixture proposals used: 'Lock the back door' (Front Door,
`lock-back-door`) and 'Check provider now' (Notes Sync, `probe-provider`, attempts 2, last error
'provider timed out')". The fixture contains **no proposals and no ActionProposal objects at all**.
`lock-back-door` is `crossViewExample.action` — the transition §9 already *applies* — so the same
event is shown both as an applied change and, afterwards, as a proposal still waiting. `probe-provider`
is `notes-sync.retry.action` with `allowed: "human"`: a person's retry inside the owning app, which
§4.9 already routes correctly as an owner handoff to Memory. Relabelling it a proposal with the
effect word "Changes the real world" misstates what it is. `studio-printer.retry`
(`retry-last-job`, attempts 1) is the same shape. Requirement 2 is explicit: "use its ids, names
and states verbatim; add nothing it does not contain" (`concept-brief-v2.md:16`).

"Decided by Home" / "Decided in Project Home" is unevidenced too: the fixture has no authority
field. The contract does (`ConnectionDescriptor.authority: "worlds" | "external"`, §4.1) and it is
UNKNOWN for these services.

**Why it matters.** Sol condition 2 — proposals are inert — is one of six pre-prototype gates
(decision 145). A gate proved on a fabricated row proves nothing about the real one, and the one
surface a person can actually see (the owner retry) now appears twice in two vocabularies.

**Concrete fix.** Choose and state one:
- **Mark the provenance honestly**: "No fixture service carries a proposal. These rows are drawn
  from the contract's `ActionProposal` shape with `authority` shown as UNKNOWN; `lock-back-door`
  appears only in its §9 applied form, and `probe-provider` stays the owner retry in §4.9." Then
  the `effect: write`, `exposed: false` and `approval` rules are stated as text under the row.
- **Or cut them** and prove condition 2 on what is fixture-true: the retry rows carry no Run
  control, say `allowed: human`, and route to the owner app; plus "an adopted external write is not
  an agent tool (`exposed: false`)" in text.

Either way, bind "Decided by …" to `authority` and show UNKNOWN where authority is unknown rather
than choosing one.

---

## Gap 5 — the read-only proof path (Sol condition 6, the gate everything waits on) cannot be walked

**What is wrong.** §10 acceptance step 2 requires "The new fact goes **Stale** …, then
**Unknown**". But §9 gives re-check schedules to exactly two services — Front Door 20s, Media Shelf
30s — and scripts the stale event for Media Shelf alone. A service connected through Connect has no
re-check schedule and no staleness rule, so nothing the person publishes can ever go Stale or
Unknown. Worse, §9 forbids re-checking Unavailable services, and Notes Sync (C1's default first
stop) is `unavailable` at fixture baseline, so it can never leave that state. The only place Stale
and Unknown appear for a *connected* service is C1's candidate list (§4.4), which shows the state
word of a service Worlds has not connected and has not read from — a reading it cannot have. The
brief's Stage C proof path (brief:18) is this same walk.

**Why it matters.** Condition 6 says the read-only path is proven first: keyboard, mobile, stale
and unknown. As specified, "stale and unknown" only appear for the two seeded services on a 90s
timer, and only if a reviewer waits for it. The gate is the one part that is unbuilt. And showing a
pre-connection state word breaks the honesty floor ("nothing presented as a real reading",
`concept-brief-v2.md:23`).

**Concrete fix.**
- **Make reactivity a rule, not a table of constants**: any connected service whose facts are live
  re-checks on a schedule derived from its own `checkedAt`; publishing a connection arms one
  scripted missed re-check for that service, labelled "simulated" exactly like Media Shelf's, with
  the same 60s escalation to Unknown and the same "Check now" restore. Write the schedule as a
  per-state rule so a fourth service needs no new line.
- **Discover says what discover can honestly say** before a reference exists: "Not connected yet ·
  no reading", candidate capabilities with `verified: false`, and the contract's own
  "`needs_auth: unknown`, never a silent none" (`connect-contract.md` §3 endpoint 1). Stale and
  Unknown are then proven on a service the person actually connected, which is what condition 6 asks.

---

## Gap 6 — the scope screen is the publish selector, so Sol condition 3 is nominal

**What is wrong.** §4.4 C2 scopes the reference to "which parts of the service the reference may
be used for (the **scope**, default all discovered facts)". In the contract,
`CredentialReference.scope` is a list of **capability ids** checked before the sender dials, and it
is what makes "a credential sent to a capability outside its scope fails with no DNS lookup"
(`connect-contract.md` §4.2, §5.1). The spec's C2 scope and its C5 Choose both tick *facts*, so the
person ticks the same facts twice for two different contract fields, and nothing says which field
each one binds to. C2's sentence — "Worlds will send this reference only to: {list}" — is therefore
a promise about facts rather than about the send path. Separately, §4.12 gives the seeded services
an "Unscoped (older connection)" row plus a "Narrow scope" control, but never says where Narrow
scope goes: those two services never passed through Discover, so there is no capability list to
narrow against.

**Why it matters.** Condition 3 is scoped auth before any network call. As written, a reviewer
checking "can Test run with no scope?" ticks the publish selector, sees the gate pass, and no scope
was ever bound to the credential.

**Concrete fix.** Name the field at every touchpoint, once:
- **C2 = the credential's send scope**, one checkbox per discovered capability, at least one, with
  "Worlds sends this reference only when reading: {list}" and a note that this is not the same as
  what appears on the counter.
- **C5 = the publish selection**, "Shown on your counter and visible to agents: …".
- **Settings** shows "Scoped to: {n} capabilities" (not facts), and **"Narrow scope"** must land
  somewhere: define it as Connect → Reference for that connection with its capabilities
  pre-filled, or state plainly that it is unavailable in this mock and why — the same treatment
  "Keep history after disconnect" gets.
- Leave Discover's candidate list unscoped and say so in words ("Looking only. No reference has
  been used yet"), which is also the truthful answer to "sends no credential".

---

## Gap 7 — a Settings toggle can switch the fail-closed approval path "connected"

**What is wrong.** §4.12 About → Mock controls offers "Show Needs you approvals as connected", and
§4.7's "Link ready" state is specified as a real link to Project Home. So one control inside the
product's own Settings — off by default, labelled a preview — turns condition 1's fail-closed
boundary into its passing state, in the same shell whose §10 gate check is "Click the handoff in
the default build and confirm nothing reads as done." Every other mock trigger in the spec (failed
test, refused frame, scripted stale) turns a *failure* on; this one turns the boundary off, and its
language ("Project Home, not Worlds, makes the decision") is precisely the copy that must not be
reachable while it is unproven.

**Why it matters.** Decision 145 makes the six conditions pre-prototype gates. A gate a visible
control can open in the shipping-shaped UI is not a gate, and it is the gate whose failure mode is
the most damaging one (an approval that looks sent).

**Concrete fix.** Move it out of the product surface: a build-time constant or a hash flag in the
prototype file, not a row in Settings, with §11 requiring the shipped mock to have it off and
unreachable from the UI. Keep the "Link ready" wording in §4.7 as a design note for the future, and
leave About to the honest list (MOCKUP, synthetic data, the §12 UNKNOWNs, "Replay the welcome",
the disabled history option). Keep the mock controls that only produce failures — they are the
prototype's job.

---

## Gap 8 — four small sentences that assert something the fixture does not

**8a. Unavailable has the wrong cause for Studio Printer.** §4.9 gives both Notes Sync and Studio
Printer the line "That service stopped answering." The fixture says of Studio Printer: "The last
job failed; **the printer is reachable** but rejected the job." The cause Worlds displays is not
the cause that happened.

**8b. The stale line erases Nightly Backup's own reason.** §4.3's Stale row replaces the slip
reason with "Nothing has changed since {time} that Worlds knows of" for every stale service, which
removes Nightly Backup's fixture summary — "Last successful run is older than the configured daily
window" — the only sentence that says *why* it is stale. Fixture text is the honesty floor
(`concept-brief-v2.md:16`); the fresh *service* (`Media Shelf`) needs different wording from an old
one.

**8c. Dead copy in the one consequential dialog.** §4.10's "Stays" column promises "1 action is
waiting for approval in Project Home. Disconnecting doesn't cancel it." With approvals fail-closed
end to end (§4.7; contract §3 endpoint 12 has no verifier, so the path is refused), nothing can
ever be pending and that line can never render. Unrenderable promises in the disconnect dialog
teach a person to distrust the sentences that are true.

**8d. Revoke has no screen.** The brief's prototype flow lists "→ revoke → disconnect"
(brief:38) and the contract separates the verbs: endpoint 13 `disconnect` stops publishing and
drops caches; endpoint 14 `revoke` deletes the config objects, purges held credentials, reports
`external_state_untouched: true` and tells the owner to revoke at the provider (§3, §4.6). §4.10
folds revoke into a checkbox inside disconnect and §4.12's "Remove" does the same thing, so
revoke's distinct consequences — the connection is gone, the held credential is purged, the
provider's own key is still out there — are compressed into one clause of a dialog about a
different verb.

**Concrete fix.**
- **(a)** One Unavailable line per cause: "That service stopped answering…" for Notes Sync; for
  Studio Printer the fixture's own sentence, with "Retry last job" as the route to Studio.
- **(b)** Always show the fixture `summary` on the slip; put "Nothing has changed since {time}…"
  under it as the freshness explanation, never in place of it.
- **(c)** Delete the pending-approval line, or render it only when something is genuinely pending —
  which in this build is never.
- **(d)** Give revoke its own confirmation with its own three-part consequence list, and state in
  §4.10 that disconnect deliberately keeps the reference (`credentials_retained`, contract §4.6)
  while revoke is the only path that deletes anything.