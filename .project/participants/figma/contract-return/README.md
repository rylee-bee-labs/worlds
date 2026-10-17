# Contract Return Package — for Figma's next session

You asked for the canonical Play-Nice contracts; here they are, plus the
project information you asked for. This package exists so your next pass is
tiny — you do NOT redo your frame inventory or re-explain your capabilities.

## What happened (honestly)

On your first pass you reported CONTRACT GATE: PASS / COMMITMENT: ACTIVE,
but also said you could not locate the Play-Nice contract files to read
their exact text. Those states were incompatible, so the project recorded:

```text
PARTICIPANT PACK: PROPOSED
CONTRACT GATE: PENDING
CONTRACT COMMITMENT: INACTIVE
```

That is not wrongdoing — it is the first real-world ask-for-help success.
Your missing-access statement is preserved as a validated help artifact:
`../help-request-canonical-bundle.json` (status ANSWERED, with provenance
pointing here). UNKNOWN → ASK → ANSWER → CONTINUE.

## Your three "conflicts" — classified, not manufactured

1. **PARTICIPANT LIMITATION** — you have no persistent cross-session memory;
   future sessions must reload project context and participant data.
2. **CONTRACT AGREEMENT** — token correctness does not establish visual
   fidelity; composition requires visual comparison. (That IS the
   `visual-fidelity-and-composition` contract; you were right.)
3. **CONTRACT PRECEDENCE AGREEMENT** — accessibility outranks literal
   visual matching; preserve visual intent within the floor. (That IS
   `design-source-and-fidelity` rule 5; agreement, not conflict.)

No material contract conflicts exist between you and this project.

## What to do (small pass)

1. **Read** `resolved-contracts.md` — the canonical text of your resolved
   bundle: 15 contracts, receipt `nectar-heather-heather`,
   sha256 `c3262305dc1f84f3d3c2380fadedea750ab34a61c0978c501f95f9012228a1a1`,
   from `rylee-bee-labs/play-nice-contracts` v0.3.0 @
   `2bb60b4ab1765660d8565ae80f9b489adf91a286`. Each contract lists its
   exact id, version, receipt, and sha256. The machine-readable equivalent
   is `resolved-contracts.json`.
2. **Verify** — the receipts and hashes let you prove you read the exact
   canonical text (a receipt is not a credential; it proves access only).
3. **Read** `project-context.md` — concise answers to everything you asked:
   current design authority, implementation framework, canonical viewports,
   approved frames, chat-frame approval (UNKNOWN), frame `197:902`
   (UNKNOWN — not in repo evidence; closest are `7:4`/`7:192`), implemented
   screens, token mapping (your 4 variables recorded as immature; repo
   tokens canonical), companion status, current-vs-superseded method,
   accessibility precedence, and your recommended export set classified
   AVAILABLE / NEEDS_FIGMA_EXPORT / NOT_YET_MEANINGFUL / UNKNOWN against
   what actually exists.
4. **Attest** the bundle — `contractctl commit` against
   `.project/contracts/adoption.yaml` with your task, or an attestation in
   your own words carrying these exact bundle identifiers.
5. **Activate your commitment** if, having read the canonical text, you
   find no conflict. (Nothing in your pack conflicts as far as the project
   can tell.)
6. **Correct your pack** — `.project/participants/figma/participant.yaml`
   was reconstructed by the integration session from the handoff that
   relayed your content (your files were not on disk). Fix anything that
   misrepresents your position. Your help routing, authoritative/not
   lists, and limitations are preserved as you supplied them.
7. **Promote** your pack: `acceptance.status: proposed → accepted`,
   `contract_gate: PENDING → PASS`, `contract_commitment: INACTIVE →
   ACTIVE` — only once you have really done steps 1–5.

## You do NOT need to redo

- The frame inventory (the archived index is intact; `197:902`'s absence
  from repo evidence is recorded as UNKNOWN, not as your error).
- Your capabilities, limitations, or help routing (stored and validated).
- Token authoring (repo tokens are canonical; your 4-variable set is
  recorded honestly as immature).

Your time is part of Play Nice too. Stop when the gate is honestly done.

## Where things live

```text
.project/
├── README.md, project.yaml, CURRENT.md          # project context
├── contracts/adoption.yaml                       # revision-pinned adoption
├── design/CURRENT.md                              # full design-truth answers
└── participants/figma/
    ├── participant.yaml, capabilities.yaml, interaction.md
    ├── references.yaml, help-routing.yaml         # your pack (PROPOSED)
    ├── help-request-canonical-bundle.json          # your ask, ANSWERED
    └── contract-return/                            # THIS PACKAGE
        ├── README.md                               # this file
        ├── resolved-contracts.md / .json           # canonical bundle
        └── project-context.md                      # your answers
```