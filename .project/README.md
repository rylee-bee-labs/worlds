# Worlds — durable project context

This directory holds **routing and durable decisions**, not a second copy of
the repository.

## Start here

1. Read [`project.yaml`](project.yaml) for project identity and canonical
   pointers.
2. Read [`CURRENT.md`](CURRENT.md) for current branch/runtime/work routing.
3. Read [`PLAN.md`](PLAN.md) when the task depends on product direction.
4. Load only the contracts and participant material that actually apply.

Then inspect the code, GitHub state, and live evidence relevant to the task.

## Three layers

```text
Play-Nice contracts
        ↓
Worlds project context
        ↓
optional participant packs
```

- Shared contracts stay in `Rylee-Bee/play-nice-contracts` and are adopted
  through [`contracts/adoption.yaml`](contracts/adoption.yaml).
- Worlds-specific truth stays in its owning source: ADRs, contracts, code,
  tests, operations docs, design sources.
- Participant packs are replaceable enrichment. They do not silently become
  canonical project truth.

The adoption manifest's pinned revision is authoritative. Do not copy its
version or SHA into prose that must then be kept in sync.

## Continuity

Git, GitHub PRs/issues, ADRs and the current-state router carry continuity.

Dated `HANDOFF-*` files in this directory are historical receipts. Keep them
when they are useful provenance, but do not require a new handoff for ordinary
session closure and do not treat an old handoff as current state.

If unfinished work must survive the session, put it in the owning GitHub issue
with an acceptance boundary.

## Participants

Participant packs live under [`participants/`](participants/).

A pack states what the participant is and is not authoritative for. Deleting a
pack should remove convenience, not project truth.

## Public boundary

This is a public repository. Project context must never contain private
deployment topology, credentials, personal data, secret values, or private
runtime logs.

The governing source is [`../SECURITY.md`](../SECURITY.md).

## Provenance

The Play-Nice project-context structure was introduced here in September 2026.
Its detailed adoption/pin history remains in Git and the adoption manifest.

Current truth should not require replaying that history.
