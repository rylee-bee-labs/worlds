# ADR-0008: the front door (meaning, mechanics, authority)

> **Status:** Accepted 2026-10-01 · **Amends:** ADR-0001 · **Relates to:** ADR-0006 (event envelope = journal entry), ADR-0007 (secrets) · **Canonical for:** the front-door architecture and its refinements · **Read this if:** you are touching providers, navigation, Memory, or how actions are authorized.

**In short:** Worlds owns meaning; providers own mechanics. The landmarks are `Home · Connect · Memory · Settings`. Executable actions have one authority path with at-most-once dispatch. Owner approval and refinements: `.project/HANDOFF-FRONT-DOOR-APPROVAL-2026-10-01.md`; baseline: `.project/PROPOSAL-FRONT-DOOR-2026-10-01.md`.

## Decision

1. Worlds owns meaning. Providers own mechanics. External systems connect as Providers. Requests carry transport. Mappings carry meaning as descriptive `concept` metadata. Cards present. Boards compose. A provider's API shape never becomes a Worlds concept.
2. Core owns a small named set of concepts: Home, Connect, Memory, Settings, and the Memory baseline (Kept, Later, Records, History, Find). They work with zero providers and zero models. Chat is optional and may be absent.
3. ADR-0001's capability registry is retired for front-door providers. Validation checks schema, secret references and confinement.
4. Authority is explicit and single-path, including Connect test/run.
   - Human UI, assistant and automation use the same governed path. A saved request is not a tool; agents see only explicit bindings their scope permits.
   - Authority and durable single dispatch exist before any side-effecting integration. Writes follow: approve → durably consume authorization → dispatch at most once → SUCCEEDED | FAILED | UNKNOWN. No automatic replay; a retry is a new action.
   - Project Home's approval stays canonical for operations it governs. For services Project Home does not govern, Worlds asks the owner directly (confirm + step-up) and keeps the bindings and receipts.
   - Agents get only narrow, bound answers about private memory.
5. Configuration is files. UI-created configuration round-trips through the documented YAML without loss. No UI-only store is canonical.
6. Presentation does not change structure. Themes and packs (Station) may change look, voice and moments. They may not move, rename, add or remove a landmark, or gate a function.
7. A clean application rebuild is authorized. Reuse good code where it fits; compatibility with the obsolete app is not a goal. Required behavior and security properties must work before production cutover.
8. Memory is durable from day one: persisted outside ephemeral containers, with restart/restore verified and a documented export path. Deterministic local search works with every model and provider off.

## Consequences

- Provider integrations become data (recipes); Python adapters shrink.
- `framework validate` and `tests/test_framework.py` change in the foundation slice.
- Room/0 integration continues unchanged as a provider kind; code calls these services.
- Station and character canon are preserved as an optional pack.
- Superseded decisions S1–S10 are listed in the proposal and carry dated notes in their source documents.
