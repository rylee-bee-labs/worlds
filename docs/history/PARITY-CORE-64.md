# PARITY-CORE-64 — orphan-route adjudication spine

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`.project/CURRENT.md`](../../.project/CURRENT.md)) · **Read this if:** you need the 2026-09-20/21 route-adjudication record for provenance · **Superseded by:** the running code and [`.project/CURRENT.md`](../../.project/CURRENT.md).

**In short:** a dated record of an overnight pass that judged 36
orphan API routes against the code (fix / document / deprecate). Since
it was written, the interface flipped to the React rebuild in `ui/`
(2026-09-22, Bridge is now home) and the server-rendered Station became a
theme package; the route table and counts below are from the
`feat/station-vnext-foundation` branch and have moved on. Truth routing:
[`docs/README.md`](../README.md).

**Track A (contract & parity), overnight run 2026-09-20/21 · branch
`feat/station-vnext-foundation` · base HEAD `9e798c3` · remote
`github.com/rylee-bee-labs/worlds` (PR #60).**

This is the parity spine the morning handoff surfaces: every route from the
`CONTRACT-TRIAGE-2026-09-20.md` "UNCONSUMED & UNDOCUMENTED (36)" list, judged
**fix / document / deprecate** against the actual code in this worktree — each
handler read, its decorators and auth dependencies checked, never guessed.

## Method (repeatable)

- Ground truth = the live FastAPI route table of `create_app()`, cross-checked
  against the curated `ENDPOINTS` table in
  [`src/personal_world/api_manifest.py`](../../src/personal_world/api_manifest.py)
  and the generated spec `ui/src/generated/openapi.json`
  (`uv run --extra crypto python scripts/gen-openapi.py`).
- Per-handler: read the function, its `dependencies=[...]`, and its docstring;
  verify the curated row's capability/kind/gate/auth or add a correct one.

### Triage correction (evidence, not opinion)

The triage file's static analysis predates this branch's manifest state. As of
base HEAD, `api_manifest.py` curates **114 rows, all `present: true` — zero
ghost rows** — and 30 of the 36 "undocumented" routes already carry accurate
curated rows (the triage parser counted 112 rows and matched `/{param}` paths
literally, so it missed the multi-line `_e(...)` rows and named path
templates). The genuinely row-less orphans were 6: `GET /`,
`GET /api/templates`, and the four static-asset routes. No route on the list
is dead: every one is registered and serves; **zero deletions tonight (rail)**.

## Verdict vocabulary

| Verdict | Meaning |
| --- | --- |
| kept-with-row | curated manifest row exists (or was added) and matches the code; route stays on the public surface |
| documented-internal | route stays working but is not part of the Lego-box API surface (UI shell / static assets); rationale recorded here and, where it was missing, a docstring in the code |
| deprecate-candidate | nothing consumes or needs it — flagged for the owner's tap, left running (no deletions tonight) |

## The 36, judged

### A1 — routes 1–9

| Method | Path | Verdict | Row / action | Rationale |
| --- | --- | --- | --- | --- |
| GET | `/` | documented-internal | none (by design) | Station entry redirect (303 → `/setup` while first-run, 302 → `/station/` after; owner decisions #11/#12). Non-`/api` surface; the manifest curates only the `/api/*` Lego box (`endpoint_manifest` filters the rest by design). |
| GET | `/api/backup` | kept-with-row | API-028 verified; added missing handler docstring | `require_auth` read under `exports`; payload includes private state — docstring and row note both say "encrypt externally, never share raw" (matches `export.backup_payload`). |
| GET | `/api/brain/provenance` | kept-with-row | API-077-provenance verified | `require_auth` read under `brain`; reports `TemplateRegistry.provenance(...)` for Nerd Mode. |
| POST | `/api/chat/test` | kept-with-row | API-012 verified | `require_auth` only; POST verb curated as `kind=read` **with the required justification note**: it changes no local state, it does spend provider quota (docstring says the same). |
| POST | `/api/connections/config/{key}` | kept-with-row | API-022 verified | `require_step_up` in code ⇒ write/step-up row is accurate. (Triage listed it as `config/{}` — named param binds the same template.) |
| GET | `/api/exports/settings` | kept-with-row | API-025 verified; added missing handler docstring | `require_auth` read; "shareable blueprint; never personal data" — docstring now states which fields that means (bones, not the person). |
| GET | `/api/exports/story` | kept-with-row | API-027 verified; added missing handler docstring | `require_auth` read; route always renders with `include_private=False` (`StoryRenderer` excludes private entries), now stated in the code. |
| GET | `/api/exports/world` | kept-with-row | API-026 verified; added missing handler docstring | `require_auth` read; portable personal config, raw secrets structurally absent (vault-stored), output still personal data — all three claims trace to `export.world_export`. |
| GET | `/api/ingress/rollups` | kept-with-row | API-078 verified | `require_auth` read over the optional Traefik provider; unconfigured ⇒ honest `not_configured`, no crash (contract already in the docstring). |

### A2 — routes 10–18 (lab + native-lab reads)

All nine are registered `GET` routes with `dependencies=[Depends(require_auth)]`,
matching their curated rows exactly; the payloads ride on read-only providers
that shell out to the external `lab` CLI or observe native state — none of them
mutate. Consumer note: none is on the CORE-64 consumed list (they serve the
homelab/Lab screens), which is why they surfaced as "unconsumed" — they stay on
the surface because the manifest contract (decision #17) is the Lego box, not
a UI-traffic hit list.

| Method | Path | Verdict | Row / action | Rationale |
| --- | --- | --- | --- | --- |
| GET | `/api/lab/deploy` | kept-with-row | API-042 verified | `require_auth` read; `LabDeploy.observe()` via lab CLI — deploy status/history, no mutation. |
| GET | `/api/lab/health` | kept-with-row | API-041 verified | `require_auth` read; `LabHealth.observe()` across services. |
| GET | `/api/lab/resources` | kept-with-row | API-044 verified | `require_auth` read; `LabResources.observe()` (VM usage). |
| GET | `/api/lab/secrets` | kept-with-row | API-043 verified | `require_auth` read; provider returns audit metadata/counts only — row note "names/metadata only; never resolved values" is true in code. |
| GET | `/api/lab/settings` | kept-with-row | API-038 verified | `require_auth` read; docstring "Settings Reconciler status via lab CLI" matches `LabSettings.observe()` (`lab settings status --json`). |
| GET | `/api/lab/settings/diff/{service}` | kept-with-row | API-040 verified | `require_auth` read; desired-vs-live drift for one service via `lab settings diff`. |
| GET | `/api/lab/state` | kept-with-row | API-037 verified | `require_auth` read; presentation-only operator packet from the lab layer (`lab-lowbw/1`). |
| GET | `/api/native-lab/health` | kept-with-row | API-046 verified | `require_auth` read; `NativeLabHealth` over the native inventory — no homelab dependency. |
| GET | `/api/native-lab/inventory` | kept-with-row | API-045 verified | `require_auth` read; `NativeLabInventory.observe()`. |

### A3 — routes 19–27 (native-lab tail, reconciler, setup, source-control)

| Method | Path | Verdict | Row / action | Rationale |
| --- | --- | --- | --- | --- |
| GET | `/api/native-lab/resources` | kept-with-row | API-048 verified | `require_auth` read; `NativeLabResources.observe()`, no homelab dependency. |
| GET | `/api/native-lab/settings` | kept-with-row | API-047 verified | `require_auth` read; `NativeLabSettings.observe()`. |
| GET | `/api/reconciler/diff/{service}` | kept-with-row | API-059 verified | `require_auth` read; computes desired-vs-observed drift; body-less or invalid-JSON requests are treated as EMPTY observed state (`_observed_from_request`) — a structured degradation, not a 500. |
| GET | `/api/reconciler/propose/{service}` | kept-with-row | API-060 verified | `require_auth` read; row note "propose only; never applies" verified — `NativeSettingsReconciler.apply()` exists as a separate method and is not routed. |
| GET | `/api/reconciler/status` | kept-with-row | API-058 verified | `require_auth` read; native reconciler observation. |
| POST | `/api/setup` | kept-with-row | API-002-run; row note enriched with the loopback fact | No auth dependency ⇒ `auth: public` is accurate; but the handler is fail-closed loopback-only (403 for remote peers) before the 409 marker check — clients need that in the manifest, so the note now says "loopback-only (403 otherwise)". |
| GET | `/api/source-control/enrichment` | kept-with-row | API-036 verified | `require_auth` read; remote-side GitHub facts only, local git stays canonical; per-status quiet degradation (`unavailable` / `not_github` / `not_configured`) all trace to real branches in the handler. |
| GET | `/api/source-control/history` | kept-with-row | API-034 verified; added missing handler docstring | `require_auth` read; native `git log`, newest-first; structured `not_configured` on unknown repo / empty search paths. |
| POST | `/api/source-control/refresh` | kept-with-row | API-035 verified; added missing handler docstring | `require_step_up` in code ⇒ write/step-up row accurate; every outcome journals (act ⇒ PROVIDER_ACTION, rejection/error ⇒ FAILURE) per the handler branches. |

### A4 — routes 28–36 (templates, updates, world writes, asset routes)

| Method | Path | Verdict | Row / action | Rationale |
| --- | --- | --- | --- | --- |
| GET | `/api/templates` | kept-with-row | **API-077-discovery added** (brain/read/none/authenticated) | Genuinely useful and documented elsewhere (`docs/brain-templates.md`, `docs/EXTERNAL-AGENT-HANDOFF.md` rely on it), only the curated row was missing. `list_public()` returns override-applied `{id, surface, role, description}` — distinct from API-077-templates' full metadata, so it is not a duplicate; the row note records the relation. |
| GET | `/api/updates` | kept-with-row | API-029 verified | `require_auth` read; apply/rollback deliberately CLI-only (destructive-confirm path) — row note matches the handler. |
| POST | `/api/world/fact` | kept-with-row | API-076-fact verified | `require_step_up` in code ⇒ write/step-up accurate. |
| POST | `/api/world/intent` | kept-with-row | API-075 verified | `require_step_up` in code ⇒ write/step-up accurate. |
| POST | `/api/world/policy` | kept-with-row | API-076-policy verified | `require_step_up`; `MutationDenied` on cemented policy → 409, matching the row note "cemented policies still refuse (409)". |
| GET | `/companions/{name}.svg` | documented-internal | no manifest row (by design); added handler docstring (was comment-only) | UI asset surface, registry **ASSET-001 ACTIVE**; `docs/p1/FOUNDATION-SPEC.md` CompanionSlot specifies this exact URL as the artwork source ("existing routes, kept"). Non-`/api`, so outside the Lego box by design. |
| GET | `/fonts/{name}` | documented-internal | no manifest row (by design); added handler docstring | Registry **ASSET-003 ACTIVE**; FOUNDATION-SPEC T5 plans `@font-face` via this route. No `@font-face` user in served CSS *today* (recorded in `docs/surfaces/ORPHANS.md` ASSET-008) — that pending wiring is the owner of the "unconsumed" flag, not deadness. |
| GET | `/icons/sprite.svg` | documented-internal | no manifest row (by design); added handler docstring | Registry **ASSET-002 ACTIVE**; 72-glyph production sprite for frontend icons. |
| GET | `/today/{name}.svg` | documented-internal | no manifest row (by design); added handler docstring | Registry **ASSET-004 ACTIVE** (consumer UI-001); allowlisted decorative exports only, no world state. |

**All 36 judged; totals: 31 kept-with-row (1 row added, 1 note enriched), 5
documented-internal, 0 deprecate-candidates.** Nothing on the list is truly
dead: every route is registered, serves, and either carries a curated row or
an ACTIVE registry/surface contract — so the honest fix was curation +
docstrings, not retirement. No deletions (rail) and none needed.

## A9 — docstring modality & certainty sweep (36 judged handlers)

Method: AST-extracted every docstring of the 36 judged handlers and screened
for certainty inflation (`guaranteed` / `always works` / `never fails` /
`100%` / `foolproof` / `cannot fail`) and may↔must↔will modality errors;
every surviving `never` / `cannot` claim was verified against its enforcing
code before being kept (chat_test's gate, backup's module contract,
lab_state's pass-through, enrichment's `_api` "never raises").

- Certainty-inflation hits: **0**.
- Modality corrections: **1** — `POST /api/setup` said "a remote peer **must
  never be able to** take over a fresh instance", an unscoped capability
  guarantee; the code proves only that non-loopback requests are refused
  here. Reworded to "cannot take over … **through this route**" — same
  meaning, true claim. Spec description re-synced.

## Full live-route spine (A5)

Ground truth at this commit: `create_app()` registers **123 paths / 143 method-paths**; curated table = **115 rows, all present (0 ghost rows)**; live `/api/*` routes still without a curated row = **11** (setup-wizard first-run flow, worlds backup/restore, OIDC logout/status — all consumed by the vnext UI, deliberately left for morning curation so mid-run Track C door-rendering stays stable). Spec: `ui/src/generated/openapi.json`, regenerated in sync.

Verdicts: **kept-with-row** (curated, verified) · **documented-internal** (non-`/api` machinery or UI asset surface — no Lego-box row by design) · **uncurated-live** (on the surface, row pending, out of tonight's 36). ★ = on the CORE-64 consumed spine.

| Method | Path | Verdict | Row / registry | Rationale |
| --- | --- | --- | --- | --- |
| GET | `/healthz` | kept-with-row | API-001 | capability health · kind read · gate none · auth public |
| GET | `/api/setup/status` ★ | kept-with-row | API-002-status | capability setup · kind read · gate none · auth public |
| POST | `/api/setup` | kept-with-row | API-002-run | adjudicated A3: capability setup · kind write · gate none · auth public |
| POST | `/api/auth/login` | kept-with-row | AUTH-009-login | capability auth · kind write · gate none · auth public |
| POST | `/api/auth/logout` | kept-with-row | AUTH-009-logout | capability auth · kind write · gate none · auth public |
| GET | `/api/auth/session` | kept-with-row | AUTH-009-session | capability auth · kind read · gate none · auth public |
| POST | `/api/auth/step-up` | kept-with-row | AUTH-009-step-up | capability auth · kind write · gate none · auth public |
| GET | `/api/auth/oidc/config` | kept-with-row | AUTH-009-oidc-config | capability auth · kind read · gate none · auth public |
| GET | `/api/auth/oidc/login` | kept-with-row | AUTH-009-oidc-login | capability auth · kind read · gate none · auth public |
| GET | `/api/auth/oidc/callback` | kept-with-row | AUTH-009-oidc-callback | capability auth · kind read · gate none · auth public |
| GET | `/api/status` ★ | kept-with-row | API-003 | capability world · kind read · gate none · auth authenticated |
| GET | `/api/daily` ★ | kept-with-row | API-004-get | capability daily · kind read · gate none · auth authenticated |
| POST | `/api/daily` ★ | kept-with-row | API-004-post | capability daily · kind write · gate none · auth authenticated |
| GET | `/api/actors` ★ | kept-with-row | API-014 | capability world · kind read · gate none · auth authenticated |
| GET | `/api/manifest` ★ | kept-with-row | API-015 | capability manifest · kind read · gate none · auth authenticated |
| POST | `/api/world/intent` | kept-with-row | API-075 | adjudicated A4: capability world · kind write · gate step-up · auth authenticated |
| POST | `/api/world/fact` | kept-with-row | API-076-fact | adjudicated A4: capability world · kind write · gate step-up · auth authenticated |
| POST | `/api/world/policy` | kept-with-row | API-076-policy | adjudicated A4: capability world · kind write · gate step-up · auth authenticated |
| GET | `/api/journal` ★ | kept-with-row | API-005 | capability journal · kind read · gate none · auth authenticated |
| POST | `/api/journal` ★ | kept-with-row | API-006 | capability journal · kind write · gate none · auth authenticated |
| POST | `/api/journal/supersede` ★ | kept-with-row | API-007 | capability journal · kind write · gate step-up · auth authenticated |
| GET | `/api/journal/history` ★ | kept-with-row | API-008 | capability journal · kind read · gate none · auth authenticated |
| PUT | `/api/journal/draft` | kept-with-row | API-080 | capability journal · kind write · gate none · auth authenticated |
| GET | `/api/journal/draft` | kept-with-row | API-081 | capability journal · kind read · gate none · auth authenticated |
| DELETE | `/api/journal/draft` | kept-with-row | API-082 | capability journal · kind write · gate none · auth authenticated |
| GET | `/api/journal/audit` ★ | kept-with-row | API-009 | capability journal · kind read · gate none · auth authenticated |
| GET | `/api/memory/search` ★ | kept-with-row | API-016 | capability memory · kind read · gate none · auth authenticated |
| POST | `/api/chat` ★ | kept-with-row | API-010 | capability chat · kind write · gate none · auth authenticated |
| GET | `/api/chat/providers` ★ | kept-with-row | API-011 | capability chat · kind read · gate none · auth authenticated |
| GET | `/api/chat/history` ★ | kept-with-row | API-010-history | capability chat · kind read · gate none · auth authenticated |
| POST | `/api/chat/test` | kept-with-row | API-012 | adjudicated A1: capability chat · kind read · gate none · auth authenticated |
| GET | `/api/tools` ★ | kept-with-row | API-013 | capability tools · kind read · gate none · auth authenticated |
| GET | `/api/brain/templates` ★ | kept-with-row | API-077-templates | capability brain · kind read · gate none · auth authenticated |
| GET | `/api/brain/provenance` | kept-with-row | API-077-provenance | adjudicated A1: capability brain · kind read · gate none · auth authenticated |
| GET | `/api/templates` | kept-with-row | API-077-discovery | adjudicated A4: capability brain · kind read · gate none · auth authenticated |
| GET | `/api/proposals` ★ | kept-with-row | PROP-list | capability proposals · kind read · gate none · auth authenticated |
| GET | `/api/proposals/{proposal_id}` ★ | kept-with-row | PROP-get | capability proposals · kind read · gate none · auth authenticated |
| POST | `/api/proposals/{proposal_id}/approve` | kept-with-row | PROP-approve | capability proposals · kind write · gate step-up · auth authenticated |
| POST | `/api/proposals/{proposal_id}/reject` | kept-with-row | PROP-reject | capability proposals · kind write · gate step-up · auth authenticated |
| POST | `/api/proposals/{proposal_id}/execute` | kept-with-row | PROP-execute | capability proposals · kind write · gate proposal · auth authenticated |
| GET | `/api/prefs` ★ | kept-with-row | API-030-get | capability prefs · kind read · gate none · auth authenticated |
| PUT | `/api/prefs` ★ | kept-with-row | API-030-put | capability prefs · kind write · gate step-up · auth authenticated |
| GET | `/api/prefs/schema` ★ | kept-with-row | API-031 | capability prefs · kind read · gate none · auth authenticated |
| GET | `/api/sections` ★ | kept-with-row | API-032-get | capability sections · kind read · gate none · auth authenticated |
| PUT | `/api/sections` ★ | kept-with-row | API-032-put | capability sections · kind write · gate step-up · auth authenticated |
| GET | `/api/apps` ★ | kept-with-row | API-066-get | capability apps · kind read · gate none · auth authenticated |
| PUT | `/api/apps` ★ | kept-with-row | API-066-put | capability apps · kind write · gate step-up · auth authenticated |
| GET | `/api/themes` ★ | kept-with-row | API-065-list | capability themes · kind read · gate none · auth authenticated |
| GET | `/api/themes/{name}` ★ | kept-with-row | API-065-get | capability themes · kind read · gate none · auth authenticated |
| GET | `/api/reminders` ★ | kept-with-row | API-067-get | capability reminders · kind read · gate none · auth authenticated |
| POST | `/api/reminders` ★ | kept-with-row | API-067-add | capability reminders · kind write · gate step-up · auth authenticated |
| PATCH | `/api/reminders/{rid}` ★ | kept-with-row | API-067-toggle | capability reminders · kind write · gate step-up · auth authenticated |
| DELETE | `/api/reminders/{rid}` ★ | kept-with-row | API-067-delete | capability reminders · kind write · gate step-up · auth authenticated |
| GET | `/api/connections/schemas` ★ | kept-with-row | API-017 | capability connections · kind read · gate none · auth authenticated |
| GET | `/api/connections/schema/{capability}` | kept-with-row | API-018 | capability connections · kind read · gate none · auth authenticated |
| GET | `/api/connections/config` ★ | kept-with-row | API-019 | capability connections · kind read · gate none · auth authenticated |
| GET | `/api/connections/overview` ★ | kept-with-row | API-020 | capability connections · kind read · gate none · auth authenticated |
| GET | `/api/connections` ★ | kept-with-row | API-021-list | capability connections · kind read · gate none · auth authenticated |
| PUT | `/api/connections` ★ | kept-with-row | API-021-save | capability connections · kind write · gate step-up · auth authenticated |
| DELETE | `/api/connections/{name}` ★ | kept-with-row | API-021-delete | capability connections · kind write · gate step-up · auth authenticated |
| POST | `/api/connections/config/{key}` | kept-with-row | API-022 | adjudicated A1: capability connections · kind write · gate step-up · auth authenticated |
| POST | `/api/connections/test` ★ | kept-with-row | API-023 | capability connections · kind read · gate none · auth authenticated |
| POST | `/api/connections/validate` ★ | kept-with-row | API-024 | capability connections · kind read · gate none · auth authenticated |
| GET | `/api/source-control/status` ★ | kept-with-row | API-033 | capability source_control · kind read · gate none · auth authenticated |
| GET | `/api/source-control/history` | kept-with-row | API-034 | adjudicated A3: capability source_control · kind read · gate none · auth authenticated |
| POST | `/api/source-control/refresh` | kept-with-row | API-035 | adjudicated A3: capability source_control · kind write · gate step-up · auth authenticated |
| GET | `/api/source-control/enrichment` | kept-with-row | API-036 | adjudicated A3: capability source_control · kind read · gate none · auth authenticated |
| GET | `/api/projects/status` ★ | kept-with-row | API-079 | capability projects · kind read · gate none · auth authenticated |
| GET | `/api/ingress/rollups` | kept-with-row | API-078 | adjudicated A1: capability ingress · kind read · gate none · auth authenticated |
| GET | `/api/lab/state` | kept-with-row | API-037 | adjudicated A2: capability lab · kind read · gate none · auth authenticated |
| GET | `/api/lab/settings` | kept-with-row | API-038 | adjudicated A2: capability lab · kind read · gate none · auth authenticated |
| GET | `/api/lab/settings/inspect/{service}` | kept-with-row | API-039 | capability lab · kind read · gate none · auth authenticated |
| GET | `/api/lab/settings/diff/{service}` | kept-with-row | API-040 | adjudicated A2: capability lab · kind read · gate none · auth authenticated |
| GET | `/api/lab/health` | kept-with-row | API-041 | adjudicated A2: capability lab · kind read · gate none · auth authenticated |
| GET | `/api/lab/deploy` | kept-with-row | API-042 | adjudicated A2: capability lab · kind read · gate none · auth authenticated |
| GET | `/api/lab/secrets` | kept-with-row | API-043 | adjudicated A2: capability lab · kind read · gate none · auth authenticated |
| GET | `/api/lab/resources` | kept-with-row | API-044 | adjudicated A2: capability lab · kind read · gate none · auth authenticated |
| GET | `/api/native-lab/inventory` | kept-with-row | API-045 | adjudicated A2: capability native_lab · kind read · gate none · auth authenticated |
| GET | `/api/native-lab/health` | kept-with-row | API-046 | adjudicated A2: capability native_lab · kind read · gate none · auth authenticated |
| GET | `/api/native-lab/settings` | kept-with-row | API-047 | adjudicated A3: capability native_lab · kind read · gate none · auth authenticated |
| GET | `/api/native-lab/resources` | kept-with-row | API-048 | adjudicated A3: capability native_lab · kind read · gate none · auth authenticated |
| GET | `/api/reconciler/status` | kept-with-row | API-058 | adjudicated A3: capability reconciler · kind read · gate none · auth authenticated |
| GET | `/api/reconciler/diff/{service}` | kept-with-row | API-059 | adjudicated A3: capability reconciler · kind read · gate none · auth authenticated |
| GET | `/api/reconciler/propose/{service}` | kept-with-row | API-060 | adjudicated A3: capability reconciler · kind read · gate none · auth authenticated |
| GET | `/api/discovery/status` ★ | kept-with-row | API-049 | capability discovery · kind read · gate none · auth authenticated |
| GET | `/api/discovery/sources` ★ | kept-with-row | API-050-get | capability discovery · kind read · gate none · auth authenticated |
| POST | `/api/discovery/sources` ★ | kept-with-row | API-050-add | capability discovery · kind write · gate step-up · auth authenticated |
| GET | `/api/discovery/interests` ★ | kept-with-row | API-051-get | capability discovery · kind read · gate none · auth authenticated |
| POST | `/api/discovery/interests` ★ | kept-with-row | API-051-add | capability discovery · kind write · gate step-up · auth authenticated |
| GET | `/api/discovery/discover` ★ | kept-with-row | API-052 | capability discovery · kind read · gate none · auth authenticated |
| GET | `/api/media/status` ★ | kept-with-row | API-053 | capability media · kind read · gate none · auth authenticated |
| GET | `/api/media/library` ★ | kept-with-row | API-054 | capability media · kind read · gate none · auth authenticated |
| GET | `/api/media/recent` ★ | kept-with-row | API-055 | capability media · kind read · gate none · auth authenticated |
| GET | `/api/media/activity` ★ | kept-with-row | API-056 | capability media · kind read · gate none · auth authenticated |
| GET | `/api/media/search` ★ | kept-with-row | API-057 | capability media · kind read · gate none · auth authenticated |
| GET | `/api/vault/status` ★ | kept-with-row | API-061 | capability vault · kind read · gate none · auth authenticated |
| POST | `/api/vault/unlock` ★ | kept-with-row | API-062-unlock | capability vault · kind write · gate none · auth authenticated |
| POST | `/api/vault/lock` ★ | kept-with-row | API-062-lock | capability vault · kind write · gate none · auth authenticated |
| GET | `/api/vault/names` ★ | kept-with-row | API-063-names | capability vault · kind read · gate none · auth authenticated |
| POST | `/api/vault/set` | kept-with-row | API-063-set | capability vault · kind write · gate none · auth authenticated |
| GET | `/api/vault/{name}` ★ | kept-with-row | API-064-get | capability vault · kind read · gate none · auth authenticated |
| DELETE | `/api/vault/{name}` ★ | kept-with-row | API-064-delete | capability vault · kind write · gate none · auth authenticated |
| GET | `/api/identity/users` ★ | kept-with-row | API-068-list | capability identity · kind read · gate none · auth authenticated |
| POST | `/api/identity/users` ★ | kept-with-row | API-069 | capability identity · kind write · gate step-up · auth authenticated |
| DELETE | `/api/identity/users/{user_id}` | kept-with-row | API-070 | capability identity · kind write · gate step-up · auth authenticated |
| GET | `/api/identity/agents` ★ | kept-with-row | API-071-get | capability identity · kind read · gate none · auth authenticated |
| POST | `/api/identity/agents` ★ | kept-with-row | API-071-create | capability identity · kind write · gate step-up · auth authenticated |
| DELETE | `/api/identity/agents/{agent_id}` | kept-with-row | API-072 | capability identity · kind write · gate step-up · auth authenticated |
| GET | `/api/identity/principal` ★ | kept-with-row | API-073 | capability identity · kind read · gate none · auth authenticated |
| PUT | `/api/identity/principal` ★ | kept-with-row | API-074 | capability identity · kind write · gate step-up · auth authenticated |
| GET | `/api/exports/settings` | kept-with-row | API-025 | adjudicated A1: capability exports · kind read · gate none · auth authenticated |
| GET | `/api/exports/world` | kept-with-row | API-026 | adjudicated A1: capability exports · kind read · gate none · auth authenticated |
| GET | `/api/exports/story` | kept-with-row | API-027 | adjudicated A1: capability exports · kind read · gate none · auth authenticated |
| GET | `/api/backup` | kept-with-row | API-028 | adjudicated A1: capability exports · kind read · gate none · auth authenticated |
| GET | `/api/updates` | kept-with-row | API-029 | adjudicated A4: capability updates · kind read · gate none · auth authenticated |
| GET | `/api/auth/oidc/logout` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| GET | `/api/auth/oidc/status` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| GET | `/api/setup-wizard/state` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| GET | `/api/worlds/backup/download/{token}` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| POST | `/api/setup-wizard/auth-choice` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| POST | `/api/setup-wizard/comfort` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| POST | `/api/setup-wizard/finish` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| POST | `/api/setup-wizard/provision` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| POST | `/api/setup-wizard/test-oidc` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| POST | `/api/worlds/backup` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| POST | `/api/worlds/restore` | uncurated-live | — | beyond tonight's 36 (consumed by vnext UI); curation task recorded for morning |
| GET | `/` | documented-internal | — | adjudicated A1: Station entry redirect (decisions #11/#12); app machinery, not the Lego box |
| GET | `/companions/{name}.svg` | documented-internal | ASSET-001 | UI asset surface, registry ASSET-001 ACTIVE; adjudicated A4 |
| GET | `/docs` | documented-internal | — | app machinery (pages / docs / redirects), not the Lego box |
| GET | `/docs/oauth2-redirect` | documented-internal | — | app machinery (pages / docs / redirects), not the Lego box |
| GET | `/fonts/{name}` | documented-internal | ASSET-003 | UI asset surface, registry ASSET-003 ACTIVE; adjudicated A4 |
| GET | `/icons/sprite.svg` | documented-internal | ASSET-002 | UI asset surface, registry ASSET-002 ACTIVE; adjudicated A4 |
| GET | `/login` | documented-internal | — | app machinery (pages / docs / redirects), not the Lego box |
| GET | `/login/` | documented-internal | — | app machinery (pages / docs / redirects), not the Lego box |
| GET | `/openapi.json` | documented-internal | — | app machinery (pages / docs / redirects), not the Lego box |
| GET | `/redoc` | documented-internal | — | app machinery (pages / docs / redirects), not the Lego box |
| GET | `/setup` | documented-internal | — | app machinery (pages / docs / redirects), not the Lego box |
| GET | `/setup/{asset}` | documented-internal | — | app machinery (pages / docs / redirects), not the Lego box |
| GET | `/today/{name}.svg` | documented-internal | ASSET-004 | UI asset surface, registry ASSET-004 ACTIVE; adjudicated A4 |

