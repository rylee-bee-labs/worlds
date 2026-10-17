# Worlds vNext | one live campaign, one preservation map

> Reviewed 2026-10-16. **Source design/acceptance truth stays in [Worlds vNext #321](https://github.com/rylee-bee-labs/worlds/issues/321), the current work issues and accepted owner decisions.** This map is a read-only issue-routing document: no implement, deploy, credential, Memory, UI/canon or protected production change occurs by moving an issue.

## Which parent is current?

- **#321 is the living owner-directed campaign:** safe cleanup → chosen visual direction + Connect API contract → small integrated prototype → tested implementation → deployment approval.
- **#312 is the earlier, historic coherence/readiness epic:** its complete original title and issue body are [archived verbatim](2026-10-16-coherence-epic-archive.md). Its unique source-truth, human-acceptance, external-first, Memory-durability, authority, rollback and public-safety requirements survive as explicit requirements below, with live child issues. Its historical links and comments stay on GitHub.
- **#262** keeps the real Phase 4 legacy/retirement cleanup and rollback evidence. Not closed; no deletion without named consumers.
- Do not infer from issue closure that old UI, current runtime, phone, screen reader or new API passes. Source merge != deployment.

## One map, existing active issues

| Responsibility | Current owner issue | Required evidence / owner gate |
|---|---|---|
| Program sequence + product direction | [#321](https://github.com/rylee-bee-labs/worlds/issues/321) | One approved design direction, typed Connect contract, secure data boundaries, prototype and release phases |
| Preserve baseline, docs/source/historical retirement | [#262](https://github.com/rylee-bee-labs/worlds/issues/262) | Current main SHA, consumers, keep/retire/UNKNOWN ledger, rollback; no unsafe bulk deletion |
| Manual accessibility and physical phone acceptance | [#314](https://github.com/rylee-bee-labs/worlds/issues/314) | Actually run screen-reader/keyboard/phone, record actual devices; NOT RUN != PASS |
| New look and phone/desktop design gate | [#322](https://github.com/rylee-bee-labs/worlds/issues/322) | Rylee selected Card deck in Mulberry & Mint mockup only; implementation and device checks still separate |
| Provider-neutral connection, auth/permission boundary | [#323](https://github.com/rylee-bee-labs/worlds/issues/323) | Client/API contract, external HTTP and room/0 consumer, no raw secrets, safe actions, rollback |
| Real chat endpoints + provider streaming | [#332](https://github.com/rylee-bee-labs/worlds/issues/332) | Real authenticated endpoint behavior, no fictitious chat sending |
| Canonical pytest/Playwright gate | [#335](https://github.com/rylee-bee-labs/worlds/issues/335) | Live required checks without unproven environment claims |
| Flaky auth-route stress test | [#343](https://github.com/rylee-bee-labs/worlds/issues/343) | Repro and stable fix at real CI timeout |
| First-run, zero-provider Home | [#357](https://github.com/rylee-bee-labs/worlds/issues/357) | C6.1 guided setup card, visible Memory, UI acceptance rather than all-clear |

Prior specific Coherence #312 discovery tickets [#313–#320](https://github.com/rylee-bee-labs/worlds/issues/312) retain their **individual existing closed/open state and historical implementation evidence**. The proposed older recipe-only UI (#320) does not automatically override the accepted *new provider-neutral Connect* direction; #323 owns the current contract. A semantic-kernel proposal (#267) does not auto-authorize replacement.

## Unique guardrails carried from historical #312

1. **Source vs actual runtime:** PR #277 brought front-door source to `main`, but actual production revision is UNKNOWN until running `/healthz`/operator evidence is obtained.
2. **Four landmarks / human language / state truth:** Home, Connect, Memory, Settings; accessible, useful at zero providers/models; do not invent green status or owner authorization.
3. **External-first and smallest native Memory:** Worlds composes human meaning; Project Home and external providers own consequential source/action/execution truth; Worlds keeps its approved local durable Memory baseline.
4. **Security, provenance, recovery:** remain public-safe, secret references rather than values, at-most-once action receipts, backup/restore, personal data isolation, named consumers before deleting old code, and rollback.
5. **Real human acceptance:** synthetic tests don't replace screen reader and physical-phone evidence; label unavailable checks UNKNOWN/NOT RUN.
6. **Owner gates:** actual deploy/cutover, production data mutation, identity/secrets/permissions, public exposure, protected art and unsafe destructive retirement require separate authority; no issue tracker migration grants any.
7. **Previous owner direction:** old "design on hold" advice is superseded; Rylee selected the new design direction with visual/UI and new Connect API delivered through the gated campaign. Choosing a mockup isn't approving code or deploying.
8. **Scope:** all legitimate unfinished work must remain attached to #321 or its existing children. If a unique requirement is found without an owner, reopen #312 and map it, never silently lose it.

**Closure rule:** Once this crosswalk and the verbatim historical archive have merged and are verifiably readable on `main`, #312 may be closed as **superseded parent tracker** (not "done"), because #321 owns the campaign and each remaining technical/human item has a real issue. #321 and all child issues remain OPEN. No automatic close for real defects.
