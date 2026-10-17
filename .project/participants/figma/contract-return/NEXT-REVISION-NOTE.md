# Adoption pin moved forward — Figma's attestation is now scoped to a prior revision

Not blocking. Not a conflict. A gap, honestly recorded (truth-and-evidence;
explicit-state) rather than silently closed.

> **Addendum 2026-09-15:** the project pin moved again, v0.6.0 → **v0.7.0**
> @ `f825ffb` (adds the always-applicable `assume-unknown` contract and
> rotates the founding `play-nice-together` receipt, 1.5.0 → 1.6.0).
> Figma's attestation is therefore now **four** revisions behind and there
> is one additional always-applicable contract she has not read. Still
> non-blocking; the re-pass below is unchanged.

## What happened

2026-09-12, later the same day as Figma's accepted pass: this project's
Play-Nice adoption (`.project/contracts/adoption.yaml`) was bumped
twice more, neither time by Figma or as part of her pack's lifecycle —
first to `d6c97db` (v0.5.0) during a bounded contract-refresh pass,
then to `0cee0652fb6f13c440b1fd9cc5d78fd87cdca8ad` (v0.6.0) during the
trunk-unification + product-identity pass (same day the project's
human-facing name changed from "Personal World" to "Project Worlds" —
irrelevant to her pack's content, noted here only for the timeline).

Figma's `attestation.yaml` remains exactly as she left it: bundle
`nectar-heather-heather`, revision `2bb60b4`, 15 contracts, gate PASS,
commitment ACTIVE. That attestation is still true for what it says —
she really did read those 15 contracts at that revision and her
task-impact sentences are still her real words for that bundle. It is
not rewritten here, and this note is not a correction of it.

## What's actually different at v0.6.0 (three bumps ahead of her attestation)

- Three new always-applicable contracts she has not read:
  `participation-and-contribution` (now 1.2.0), `mutual-contribution`
  (now 1.1.0), and `collaborative-good-faith` (1.0.0, new in v0.6.0).
  All three were read in full by the foreman across the two bumps;
  none contradicts anything in her existing pack — if anything, her
  pack already models their spirit (explicit `authoritative_for` /
  `not_authoritative_for` boundaries, honest `limitations`, no claim of
  authority she doesn't have, and her recorded interactions were never
  hostile or status-based — `collaborative-good-faith` compliant by
  construction).
- Two contracts in her original 15 changed version:
  `ask-for-help` 1.0.0 → 1.3.0 (scope-negotiation + safe-uncertainty
  vocabulary added across three bumps; no change to her existing
  task-impact sentence's meaning) and `human-reliability` 1.0.0 → 1.1.0
  (negotiated human contribution language added; same).
- The other 13 contracts in her bundle are byte-identical at v0.6.0
  (verified programmatically against the new lock file: same version,
  same sha256, both bumps).

## Why this isn't fabricated on her behalf

`attestation.yaml`'s own header is explicit: "the foreman does not
fabricate her words." A real re-attestation needs Figma's own
task-impact sentences for the 3 new + 2 changed contracts, relayed the
same way her original 15 were (conversation, because her sandbox
filesystem does not persist writes — see
`help-response-write-persistence.json`). Nobody did that this session;
this note exists so the gap is visible instead of silently absorbed
into a claim that isn't true yet.

## Why this isn't blocking

Participant packs are enrichment, never canonical truth
(`project-context-and-participant-packs`) — the project does not stop
working because one optional pack is one revision behind. Nothing in
the newly-applicable contracts changes what Figma is authoritative for
(`participant.yaml`'s `authoritative_for` / `not_authoritative_for`
lists are unaffected).

## The tiny next pass, if/when there's a live Figma session again

1. Give her this note plus the three new contract bodies
   (`contracts/core/PARTICIPATION_AND_CONTRIBUTION.md`,
   `contracts/core/MUTUAL_CONTRIBUTION.md`,
   `contracts/core/COLLABORATIVE_GOOD_FAITH.md`) and the two changed
   ones at their current versions.
2. She writes five real task-impact sentences (one per contract).
3. Foreman applies them to `attestation.yaml` (bundle → new receipt,
   `loaded` → 18 entries, revision → `0cee0652fb6f13c440b1fd9cc5d78fd87cdca8ad`),
   same verify-on-disk-before-promoting discipline as the original
   re-pass.
4. `participant.yaml`'s `acceptance` block updates to reference the
   new bundle.
5. Separately, and only if useful: her project-specific references
   (`references.yaml` frame IDs) could be reviewed against the product
   rename at the same time — not because the rename invalidates them
   (it doesn't; same file, same screens), but because it's a natural
   moment to ask her whether anything in the live Figma file has moved
   on since 2026-09-07. Not required; her references were re-reviewed
   and left as-is during the 2026-09-12 identity pass (see
   `.project/CURRENT.md`).

Until then: `attestation.yaml` stays exactly as she wrote it, correctly
labeled as scoped to `2bb60b4`, and this note is the honest record of
the gap.
