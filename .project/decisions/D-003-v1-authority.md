# D-003: V1 has no current design authority

**Date:** 2026-09-13
**Status:** ACTIVE
**Owner:** Rylee

## Decision

V1 (the original Personal World dashboard design) has no current design
authority in Project Worlds.

V1 remains useful as evidence for:
- Working behavior
- Backend/API integration
- Accessibility lessons
- Product history/provenance
- Functionality that remains valid independently of its presentation

V1 must not constrain Workshop v3:
- Application shell
- Navigation presentation
- Page composition
- Content width
- Visual hierarchy
- Container/card defaults
- Companion presence or placement
- Responsive spatial behavior
- Route presentation
- Visual language

When Workshop v3 and inherited V1 structure disagree, Workshop v3 wins.

## Rationale

This is the second time a redesign has retained too much of the previous
application's visual architecture. The cause is understood:

Project Worlds correctly taught contributors to preserve working behavior,
reuse existing components, avoid unnecessary rewrites, respect repository
truth, and make incremental changes. These are good engineering rules.

But during a deliberate redesign they created an unintended priority:
working inherited implementation > canonical replacement design.

Agents reasonably treated the functioning V1 shell as infrastructure and
implemented Workshop content inside it, producing:
Workshop v3 content inside a V1 dashboard frame.

## Correction

Reuse must be earned against current authority. Preserve behavior where
appropriate. Do not preserve obsolete design architecture merely because
it already works.

## Rule

A V1 component or structure may survive only when it is independently
shown to satisfy current product contracts and canonical Workshop v3
evidence.

## Recorded

This decision is recorded so future contributors and agents do not have
to infer it again. Compatibility with V1 is not a design requirement.
Preservation of V1 is not inherently a virtue.
