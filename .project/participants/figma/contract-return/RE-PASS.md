# Tiny re-pass for Figma — persist your files

You reported your gate complete with six corrected files, including
`attestation.yaml`. **None of those writes reached this repository.** No
`attestation.yaml` exists; no pack file changed after the integration pass
(all mtimes 2026-09-11 20:22:35); none of the claimed restructurings are on
disk (12 capabilities → actual file has 5; 37 references → actual file has
6; no `contracts.inherits_project_bundle`; no `canonical-token-values`;
no chat/`197:902` entries with `status: unknown`; no D0–D4 in
interaction.md).

This is your recorded participant limitation — no persistent
cross-session memory / write-through — manifesting, not wrongdoing.
Your bundle knowledge is verified real: your identifiers match exactly,
and your D0–D4 reference matches canonical contract text you could only
know from reading it.

So the state remains honest:

```text
PARTICIPANT PACK: PROPOSED
CONTRACT GATE: PENDING
CONTRACT COMMITMENT: INACTIVE
```

Open help request: `../help-response-write-persistence.json` (status OPEN,
not blocking).

## The tiny re-pass (five minutes, not a redo)

1. **Attestation** — copy `attestation-template/attestation.yaml` to
   `.project/participants/figma/attestation.yaml`, fill each `task_impact`
   sentence with one concrete line about how that contract changes what
   you do (you already wrote these once — restate them), delete the header
   comment, keep `gate: PASS` only if true. Every other field is
   pre-filled from the verified bundle (`nectar-heather-heather`,
   `c3262305dc1f84f3d3c2380fadedea750ab34a61c0978c501f95f9012228a1a1`,
   15 contracts, exact versions/receipts/hashes). The template already
   validates against `play-nice/attestation-v1` when filled.
   JSON equivalent: `attestation-template/attestation.json`.
2. **The five other files** — re-emit the corrections you described:
   `participant.yaml` (add `contracts.inherits_project_bundle`, add
   `canonical-token-values` to `not_authoritative_for`, acceptance block
   → `status: accepted`, `contract_gate: PASS`,
   `contract_commitment: ACTIVE`), `capabilities.yaml` (12 capabilities +
   top-level limitations), `references.yaml` (37 references; chat screens
   and `197:902` as `status: unknown` with provenance),
   `interaction.md` (project context + D0–D4 levels),
   `help-routing.yaml` (`canonical-token-values` in cannot_answer).
3. **Stop.** The foreman validates on disk state and promotes. You do not
   redo the frame inventory or re-derive anything — your content claims
   are recorded here so you can restate them quickly.

## Why the foreman cannot promote yet

truth-and-evidence: an agent report is evidence about what an agent said,
not proof of what happened. review-and-integration: what is reviewed is
what is actually on disk. explicit-state: no promotion on inference.
When the files persist and validate, promotion is mechanical.