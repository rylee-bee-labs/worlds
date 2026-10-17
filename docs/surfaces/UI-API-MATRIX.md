# UI → API MATRIX — Project Worlds

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** which API surface each UI action reads or writes (the prose view of `api_manifest.py`) · **Read this if:** you need to know what a screen calls, and what gate that call passes

**In short:** Maps UI actions onto API IDs and their read/write gate. The API-side rows are still code-verified; the `UI-*` IDs name the retired 2026-09-22 SPA, so the current screens are listed separately below.

**Note (2026-09-26):** `UI-*` IDs below name the retired SPA (deleted `frontend/`
tree). The current interface is `ui/`; its screens and their main calls:

| Screen (`ui/src/screens/`) | Main calls |
|---|---|
| Bridge (home) | API-085 `/api/briefing`, API-088 `/api/rooms`, API-089 `/api/crew` |
| Memory | API-005 journal, API-016 memory search |
| Chat | API-010 `/api/chat`, API-011 providers |
| Settings | API-030/031/032 prefs + sections, connections, identity |
| Crew (from Settings/Bridge) | API-089 `/api/crew*`, keeper/doorway PUT |
| Interests | API-049..052 discovery (`/api/discovery/*`) |
| (Workshop room drawer) | API-090 `/api/secrets/overview` (admin only) |

| UI ID | Action/Data | API ID | Read/Write | Current state |
|---|---|---|---|---|
| UI-001 Today | world summary + greeting | API-003 | Read | ACTIVE |
| UI-001 Today | daily digest | API-004 (GET) | Read | ACTIVE |
| UI-001 Today | run daily loop | API-004 (POST) | Write | ACTIVE |
| UI-001 Today | reminders | API-067 (GET) | Read | ACTIVE |
| UI-001 Today | apps launcher | API-066 (GET) | Read | ACTIVE |
| UI-002 Interests | discovery status/sources/interests/discover | API-049..052 | Read / Write (source POSTs step-up gated; adding an interest is a signed-in person's own write, no step-up) | ACTIVE |
| UI-003 Media | status/library/recent/activity/search | API-053..057 | Read | ACTIVE |
| UI-004 Projects | estate status | API-079 | Read | ACTIVE |
| UI-004 Projects | repo status/history | API-033, API-034 | Read | ACTIVE |
| UI-004 Projects | approved repo refresh | API-035 | Write (step-up) | ACTIVE (propose→approve→act workflow #1) |
| UI-004 Projects | GitHub enrichment | API-036 | Read | ACTIVE |
| UI-005 Lab | lab state/health/deploy/secrets/resources/settings | API-037..044 | Read | ACTIVE |
| UI-005 Lab | native lab inventory/health/settings/resources | API-045..048 | Read | ACTIVE |
| UI-005 Lab | reconciler status/diff/propose | API-058..060 | Read | ACTIVE |
| UI-005 Lab | ingress rollups | API-078 | Read | ACTIVE |
| UI-006 Journal | list events | API-005 | Read | ACTIVE |
| UI-006 Journal | write note | API-006 | Write | ACTIVE |
| UI-006 Journal | supersede (correction) | API-007 | Write (step-up) | ACTIVE |
| UI-006 Journal | correction chain | API-008 | Read | ACTIVE |
| UI-006 Journal | audit view | API-009 | Read | ACTIVE |
| UI-007 Vault | status/names | API-061, API-063 (GET) | Read | ACTIVE |
| UI-007 Vault | unlock/lock | API-062 | Write (bearer only, not step-up) | ACTIVE |
| UI-007 Vault | set/delete | API-063 (set), API-064 (delete) | Write (bearer only, not step-up) | ACTIVE |
| UI-007 Vault | get value | API-064 | Read (loopback/private) | ACTIVE |
| UI-008 Chat | send message (+history, +route context) | API-010 | Read+model write (journal recommendation event) | ACTIVE |
| UI-008 Chat | providers list | API-011 | Read | ACTIVE |
| UI-008 Chat | correction draft (proposal) | API-007 (after human approval) | Write (step-up) | ACTIVE |
| UI-009 Settings | prefs get/put | API-030 | Read / Write (person-only, no step-up) | ACTIVE |
| UI-009 Settings | prefs schema | API-031 | Read | ACTIVE |
| UI-009 Settings | sections get/put | API-032 | Read / Write (step-up) | ACTIVE |
| UI-009 Settings | apps get/put | API-066 | Read / Write (step-up) | ACTIVE |
| UI-009 Settings | provider probe | API-012 | Read (spends quota) | ACTIVE |
| UI-009 Settings | identity principal read/update | API-073, API-074 | Read / Write (person-only, no step-up) | ACTIVE |
| UI-010 SetupWizard | setup status + bootstrap | API-001 (setup_needed), API-002 | Write (public, first-run) | ACTIVE |
| UI-011 Login | local token login | AUTH-009 (POST /api/auth/login) | Write (session) | ACTIVE |
| UI-011 Login | OIDC config | AUTH-009 (/api/auth/oidc/config) | Read | ACTIVE |
| UI-012 World | world summary/actors | API-003, API-014 | Read | ACTIVE |
| UI-012 World | intent/fact/policy quick actions | API-075, API-076 | Write (step-up) | ACTIVE |
| UI-014 SectionNav | section order/hidden | API-032 | Read / Write (step-up) | ACTIVE |
| UI-016 CompanionPresence | companion art | ASSET-001 | Read | ACTIVE |
| UI-021 ConnectionsPanel | schemas/overview/config | API-017..020 | Read | ACTIVE |
| UI-021 ConnectionsPanel | save/delete connection, native config | API-021, API-022 | Write (step-up in-handler) | ACTIVE |
| UI-021 ConnectionsPanel | test/validate | API-023, API-024 | Read (probe) | ACTIVE |
| UI-018 StepUpPrompt | step-up grant | AUTH-009 (POST /api/auth/step-up) | Write | ACTIVE (grant is persisted and consumed by `require_step_up`, D1–D3) |
| UI-005 Lab (settings) | prefs/sections (Settings owns) | API-030/032 | — | Settings screen only |
| UI-003 Media | themes (none) | API-065 | — | API exists; no UI consumer found |
| (no UI) | theme packs | API-065 | Read | PARTIAL (no frontend consumer found) |
| (no UI) | identity admin users | API-068..070 | Read/Write | ACTIVE API, no visible UI surface |
| (no UI) | brain-write proposal review (list/approve/reject/execute) | `/api/proposals*` (not in original API-ID list) | Read / Write (step-up) | ACTIVE API + durable store, no frontend consumer |
| (no UI) | updates apply/rollback | CLI-018 | Write | deliberately CLI-only |
| (no UI) | backup | API-028, CLI-008 | Read | ACTIVE (external encryption expected) |

Note: the `ui/` app boot-fetches API-030 (prefs) and the sections layout
before first paint (`ui/src/app/App.tsx`).

Machine-readable form: `src/personal_world/api_manifest.py` is the single
curated source for `{id, method, path, capability, kind, gate, auth}`,
served as the `endpoints` key of `GET /api/manifest` and verified against
the live route table on every request. Update that module — not this
table — when a route's gate or kind changes; this file stays the prose
view. It also reports `writes_without_elevation`, the writes the code
gates with `require_auth` only, which is where this matrix's "Write"
column and the enforced gate diverge (decision #17 wants that visible).