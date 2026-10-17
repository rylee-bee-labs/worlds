# PROJECT WORLDS — WIRING COMPLETION HANDOFF
# Everything that remains. All questions. All data.
# Review on a bigger screen, then paste back your answers.

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/CURRENT.md`) · **Read this if:** you need the pre-merge 2026-09-13 handoff and its 10 open questions. · **Superseded by:** `.project/CURRENT.md`.

**In short:** a pre-merge 2026-09-13 handoff listing 10 open wiring questions (companion, media, apps, themes, identity, ingress, write tools, chat-provider tools, lab endpoints, reconciler apply). All were resolved before the architecture branch merged. See [FINAL-RECEIPT.md](FINAL-RECEIPT.md) for that era's state; treat nothing here as current.

---

## STATUS: 90% WIRED

**Working end-to-end:**
- 13 screens with real API data
- 78 API endpoints all wired to domain operations
- 19 brain tools callable at runtime
- Ollama tool-calling loop functional
- Compose boots core + ollama + model

**Not wired (this handoff):**
- 6 surfaces need decisions
- 3 surfaces need minor wiring
- 1 architectural decision needed

---

## QUESTION 1: COMPANION WIRING

**Problem:** CompanionPresence, WorldScreen, and CompanionPopover all hardcode "The Mermaid" instead of reading the user's companion preference.

**What exists:**
- `companion-context.tsx` has 5 companions: personal-world, mermaid, robot, world-tree-squirrel, taco-news-truck
- `useCompanion()` hook returns the active companion
- SettingsScreen already reads/writes companion preference
- CompanionSlot primitive already reads from context

**What's broken:**
- `CompanionPresence.tsx` (sidebar bottom) — hardcoded mermaid SVG
- `WorldScreen.tsx` companion section — hardcoded "The Mermaid" text
- `CompanionPopover.tsx` — identity works, status text hardcoded

**Decision needed:**
Should I wire these to `useCompanion()` so they reflect the user's actual choice?

**If yes:** ~30 minutes of wiring. Read companion from context, render the right SVG and name.

---

## QUESTION 2: MEDIA SCREEN

**Problem:** MediaScreen is a stub. No media provider exists.

**What exists:**
- `/api/media` endpoint does NOT exist
- No media provider in the codebase
- The screen shows an honest "not_configured" empty state

**Options:**
A. **Leave as stub** — "not_configured" is a valid Project Worlds state
B. **Wire to discovery** — the discovery engine already finds content; media could show discovered items
C. **Build a media provider** — would need to know what media sources (RSS, Plex, books, etc.)

**Decision needed:**
Which option? If B, I can wire it now. If C, I need to know what media sources matter.

---

## QUESTION 3: APPS SCREEN

**Problem:** `/api/apps` exists (read/write service launcher registry) but has no UI.

**What exists:**
- `GET /api/apps` — reads `apps.json` (list of {id, name, url, icon, category})
- `PUT /api/apps` — replaces the registry (step-up gated)
- Frontend hook `useApps()` exists but no screen uses it

**Options:**
A. **Wire into Settings** — add an "Apps" panel to SettingsScreen
B. **Build a dedicated Apps screen** — `/apps` route with CRUD
C. **Defer** — apps.json is config-only, no runtime impact

**Decision needed:**
Which option? If A or B, I can wire it now.

---

## QUESTION 4: THEMES

**Problem:** `/api/themes` exists but has no UI.

**What exists:**
- `GET /api/themes` — lists available theme packs
- `GET /api/themes/{name}` — gets a specific theme
- Frontend hook `useThemes()` exists but no screen uses it
- Themes are artwork packages for companions

**Options:**
A. **Wire into Settings** — add a "Themes" panel under appearance
B. **Defer** — themes are cosmetic, no functional impact

**Decision needed:**
Which option?

---

## QUESTION 5: IDENTITY / MULTI-USER

**Problem:** 8 identity endpoints exist but have no admin UI.

**What exists:**
- `GET /api/identity/principal` — read caller's identity (WIRED — all screens use it)
- `PUT /api/identity/principal` — set display name (NOT WIRED)
- `GET /api/identity/users` — list users
- `POST /api/identity/users` — create user
- `DELETE /api/identity/users/{user_id}` — disable user
- `GET /api/identity/agents` — list agents
- `POST /api/identity/agents` — create agent
- `DELETE /api/identity/agents/{agent_id}` — disable agent

**Options:**
A. **Wire principal display name** — add to Settings profile section
B. **Build admin panel** — user/agent management under Settings → Advanced
C. **Defer** — single-user mode works without this

**Decision needed:**
Which option? If A, I can wire it now (simple). If B, need to know priority.

---

## QUESTION 6: INGRESS

**Problem:** `/api/ingress/rollups` exists but has no UI.

**What exists:**
- `GET /api/ingress/rollups` — Traefik ingress route data
- `TraefikIngress` provider auto-registered
- No frontend hook

**Options:**
A. **Wire into Lab** — add an "Ingress" panel under Lab → Network
B. **Defer** — ingress is infrastructure detail

**Decision needed:**
Which option?

---

## QUESTION 7: WRITE BRAIN TOOLS

**Problem:** All 19 brain tools are read-only. The model can't write.

**What exists:**
- Tool registry supports `requires_approval` and `requires_step_up` fields
- `_chat_with_tools_loop` handles tool execution
- Write operations exist: journal write, vault set, world writes, prefs save, etc.

**What's missing:**
- No approval flow for brain-initiated writes
- No UI to approve/reject brain proposals

**Options:**
A. **Add write tools with step-up** — brain proposes, user approves in chat UI
B. **Add write tools with no approval** — brain can write directly (risky)
C. **Defer** — read-only tools are useful as-is

**Decision needed:**
Which option? If A, I need to know the approval UX (inline chat confirmation? separate approval screen?).

---

## QUESTION 8: CHAT PROVIDER TOOL-CALLING

**Problem:** Only Ollama has `chat_with_tools`. OpenAI, Anthropic, OpenCode don't.

**What exists:**
- `OllamaChat.chat_with_tools()` — sends tools to Ollama, handles tool_calls response
- `OpenAICompatChat` — no tool support
- `OpenAIChat` — no tool support
- `AnthropicChat` — no tool support
- `OpenCodeChat` — no tool support

**Impact:**
- Tool-calling only works with Ollama (the default)
- If user swaps to OpenAI/Anthropic, brain can discuss but not invoke tools

**Options:**
A. **Add tool support to OpenAICompatChat** — OpenAI API supports tools natively
B. **Add tool support to AnthropicChat** — Claude supports tool use
C. **Defer** — Ollama is the default, other providers are opt-in

**Decision needed:**
Which option? If A or B, I can add it.

---

## QUESTION 9: REMAINING LAB ENDPOINTS

**Problem:** 4 homelab Lab endpoints have no brain tool.

| Endpoint | Brain tool? |
|----------|-------------|
| `/api/lab/settings/inspect/{service}` | ❌ |
| `/api/lab/settings/diff/{service}` | ❌ |
| `/api/lab/deploy` | ❌ |
| `/api/lab/secrets` | ❌ |

**These are homelab enrichment** — they require the Lab CLI and only work in Rylee's deployment.

**Options:**
A. **Add brain tools** — model can inspect homelab state
B. **Defer** — native lab tools cover the portable product

**Decision needed:**
Which option?

---

## QUESTION 10: RECONCILER APPLY

**Problem:** Reconciler can inspect and diff but can't apply changes.

**What exists:**
- `GET /api/reconciler/status` — services with desired state
- `GET /api/reconciler/diff/{service}` — desired vs observed
- `GET /api/reconciler/propose/{service}` — proposed actions
- No `POST /api/reconciler/apply` endpoint

**Options:**
A. **Build apply endpoint** — `POST /api/reconciler/apply/{service}` with approval
B. **Defer** — inspection is useful without mutation

**Decision needed:**
Which option?

---

## QUICK REFERENCE: WHAT I CAN WIRE RIGHT NOW (no decisions needed)

These are purely mechanical wiring tasks:

1. **CompanionPresence** → read `useCompanion()`, render correct SVG + name
2. **WorldScreen companion** → read `useCompanion()`, render correct name + description
3. **CompanionPopover status text** → read from world status instead of hardcoded
4. **Principal display name** → add to Settings profile section
5. **Lab settings/inspect/diff brain tools** → add to tool registry

---

## COPY-PASTE ANSWER FORMAT

Paste back with your answers:

```
1. COMPANION WIRING: yes / no
2. MEDIA SCREEN: A / B / C (describe if C)
3. APPS SCREEN: A / B / C
4. THEMES: A / B
5. IDENTITY: A / B / C
6. INGRESS: A / B
7. WRITE BRAIN TOOLS: A / B / C
8. CHAT PROVIDER TOOLS: A / B / C
9. LAB ENDPOINTS: A / B
10. RECONCILER APPLY: A / B

QUICK WIRE: yes / no (items 1-5 above)
```

---

## FILE LOCATIONS

| File | Path |
|------|------|
| This handoff | `docs/WIRING-COMPLETION-HANDOFF.md` |
| Full inventory | `docs/FULL-SYSTEM-INVENTORY.md` |
| API wiring | `docs/API-WIRING-HANDOFF.md` |
| Compose | `compose.yaml` |
| Connections | `config/connections.json` |
| Tool registry | `src/personal_world/tool_registry.py` |
| Chat module | `src/personal_world/chat.py` |
| API endpoints | `src/personal_world/api.py` |
| Frontend hooks | `frontend/src/lib/hooks.ts` |
| Frontend API client | `frontend/src/lib/api.ts` |
| Companion context | `frontend/src/lib/companion-context.tsx` |
