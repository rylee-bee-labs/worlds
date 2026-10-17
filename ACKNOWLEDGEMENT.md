# Acknowledgement 🐝

Project Worlds **accepts and implements**
[Play-Nice Contracts](https://github.com/Rylee-Bee/play-nice-contracts)
as its shared cooperation and engineering constitution. This page states
that plainly and points back home.

##  IMPLEMENTS PLAY NICE

This is a **downstream project claim** — not certification, audit, or
endorsement by the Play Nice project. Canonical semantics of the stamp:
[Play-Nice `docs/ACKNOWLEDGEMENT.md`](https://github.com/Rylee-Bee/play-nice-contracts/blob/main/docs/ACKNOWLEDGEMENT.md).

- **Targets:** Play-Nice library **v0.7.0**, revision
  `f825ffb1a0b49c054bbf54e0ba3c0b15441e3f0e` — the pin in
  [`.project/contracts/adoption.yaml`](.project/contracts/adoption.yaml).
- **Always-applicable contracts implemented:** `assume-unknown`,
  `ask-for-help`, `truth-and-evidence`, `human-reliability`,
  `recovery-and-reversibility`, `provenance-and-audit`, `explicit-state`,
  `stable-truth-replaceable-machinery`, `participation-and-contribution`,
  `mutual-contribution`, `collaborative-good-faith` — plus the `triggers`
  map for UI, API, CLI, security, agent, engineering, and design work.
- **Evidence:** [`AGENT_CONTRACTS.md`](AGENT_CONTRACTS.md) is the contract
  index that routes agents to these floors; [`docs/README.md`](docs/README.md)
  names the canonical source per subject; the repository gates are
  `tests/test_public_safety.py`, `tests/test_docs.py`, and
  `personal-world framework validate`.
- **Gate:** re-attested 2026-09-15 with the real `contractctl` tool
  against the pinned revision: `adopt` = ADOPTION VALID (always=11,
  triggers=9); `commit` = CONTRACT COMMITMENT ACTIVE (bundle
  `dovetail-harbor-prairie`, 11 contracts).

## What we did NOT adopt

- We do not vendor or depend on the Play-Nice tooling
  (`tools/contractctl`); it stays in the shared library. Where the
  project-context workflow resolves contracts, it runs against the
  canonical library using this project's adopted manifest
  (`.project/contracts/adoption.yaml`). Day-to-day agent contract
  behaviour is governed by this repository's own `AGENT_CONTRACTS.md`
  and `docs/accessibility/`.
- We did not copy the canonical contracts into this repository.
  The canonical home is the Play-Nice Contracts repository.

## What we owe Play-Nice

Per the Play-Nice voluntary acknowledgement pattern, we owe Play
Nice:

- a friendly acknowledgement when we share lessons learned (see
  "Send a letter back" below)
- the same honesty contract Play-Nice asks of everyone: truth
  before reputation, evidence before claims, UNKNOWN when not
  checked

We do NOT owe Play-Nice:

- this project's source code
- our data, our world, or our customer's data
- our proprietary machinery

## Send a letter back

If you fork Project Worlds and find a contract edge case, a
failure mode, an interoperability lesson, an accessibility lesson,
a provenance technique, a recovery pattern, an implementation
technique, a conformance difficulty, a case study, or a
documentation improvement that would help Play-Nice itself,
open an issue or pull request on the canonical Play-Nice
Contracts repository.

Failure letters are welcome. The judge is also a participant.

🐝
