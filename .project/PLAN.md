# Plan — Worlds

This file owns **product direction**, not task state.

Current product architecture: [ADR-0008 — the front door](../docs/adr/0008-front-door.md).

Fresh-ground machine-model proposal:
[ADR-0009 — Play-Nice semantic kernel](../docs/adr/0009-play-nice-semantic-kernel.md)
and [its executable plan](../docs/rebuild/PLAY-NICE-KERNEL-PLAN.md).

Current work: GitHub Issues. Current code/runtime state:
[`CURRENT.md`](CURRENT.md).

Which document owns which command or claim (routes, build, install, tests,
backup) — and which pages are superseded — is
[`docs/vnext/docs-truth.md`](../docs/vnext/docs-truth.md). Prefer it and
the generated inventories over a hand-copied list in any direction doc.

## North star

Things come to the person.

Worlds should gather what changed, what needs attention, what can wait, and
what is interesting without requiring someone to hunt through tools or remember
where everything lives.

It should stay useful on a low-capacity day and still open all the way down for
deep inspection when wanted.

Fun, personality and visual character are requirements. They do not get to
hide state, move structural landmarks, or weaken accessibility.

## Current front door

The stable landmarks are:

```text
Home · Connect · Memory · Settings
```

- **Home** gathers useful cards and calm attention.
- **Connect** describes outside capabilities in shared language; native/provider mechanics stay at adapters.
- **Memory** keeps durable personal state with deterministic local search and
  understandable export/restore.
- **Settings** owns configuration and comfort without lowering the
  accessibility floor.

Worlds owns product meaning. Play-Nice owns shared cooperation language.
Native systems keep their own language behind adapters.

A provider's API shape must not become the product's vocabulary.

## Experience rules

1. Real state before decorative certainty.
2. One obvious path before several clever paths.
3. Important exceptions before routine success.
4. Technical depth stays reachable through progressive disclosure.
5. Configuration round-trips through documented files. No invisible UI-only
   canon.
6. Personal state has explicit ownership.
7. Consequential actions use one authority path and leave receipts.
8. Themes and character packs may change presentation, voice and moments, not
   product structure.
9. Small slices should end in something a person can actually inspect.
10. Production cutover is an owner decision, separate from source readiness.

## Rebuild lane — merged

The front-door rebuild authorized by ADR-0008 is now `main`: `main`
carries the front door, merged from `rebuild/front-door` in PR #277
(2026-10-06). That was a source cutover. Merging publishes an image; it is
not a deployment, and it is not a production cutover.

Issues #262 and #263 were closed as `not_planned` on 2026-10-07, but
[#262](https://github.com/rylee-bee-labs/worlds/issues/262) was later
**reopened** for the remaining source-retirement and cutover work. #263 remains
closed. The historical [`docs/BACKLOG.md`](../docs/BACKLOG.md) preserves the
October 7 census; it does not supersede live issue state. The current gated
vNext campaign is [#321](https://github.com/rylee-bee-labs/worlds/issues/321),
with visual direction [#322](https://github.com/rylee-bee-labs/worlds/issues/322)
and Connect API [#323](https://github.com/rylee-bee-labs/worlds/issues/323).
[Issue crosswalk](../docs/vnext/2026-10-16-issue-crosswalk.md) keeps prior
preservation and owner gates visible.

Documents that describe `main` as pre-front-door, or `rebuild/front-door`
as the live lane, predate the merge. Keep their content and label it; do
not read their branch claims as current direction.

ADR-0009 proposes a fresh-ground semantic-kernel experiment, **not an
approved implementation sequence**. The current vNext direction in #321 and
provider-neutral Connect contract in #323 take precedence over that earlier
proposal. Any replacement must first prove consumers, durable data and rollback,
then receive the actual authority/owner approvals. Do not build or delete the
kernel solely because ADR-0009 is linked here. Implementation, when justified,
must live in bounded GitHub issues; this file is not a hidden backlog.

## Preserve

Keep recoverable:

- character and companion canon,
- deliberate artwork and source rigs,
- accessibility and human-reliability contracts,
- accepted ADRs and decision history,
- export/restore paths for durable state,
- the preserved pre-front-door source/runtime rollback handles until cutover is
  accepted and verified.

## Parked ideas are not commitments

Older plans mention specific inboxes, media integrations, social sources,
Workbench/Node ideas, visual directions and implementation sequences.

Those are idea/history sources. They do not authorize work simply because they
remain in Git.

Promote an idea by making the current architecture decision and bounded work
explicit.

## Done

A source slice can be complete without being deployed.

A production change is complete only when:

```text
source ready
→ relevant gates pass
→ review/integration complete
→ owner approves cutover/deploy
→ runtime revision verified
→ rollback remains understandable
```

Green CI is necessary evidence. It is not the same thing as "Rylee is now
running this."
