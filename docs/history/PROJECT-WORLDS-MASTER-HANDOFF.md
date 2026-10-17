# PROJECT WORLDS — MASTER HANDOFF

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`.project/CURRENT.md`](../../.project/CURRENT.md)) · **Read this if:** you want the dated 2026-09-16 "everything in one file" handoff for provenance · **Superseded by:** [`.project/PLAN.md`](../../.project/PLAN.md) for direction and [`.project/CURRENT.md`](../../.project/CURRENT.md) for state.

**In short:** a 2026-09-16 top-down handoff (what it is, what was built,
what was in flight, the decision list). Since it was written, the interface
flipped to the React rebuild in `ui/` (2026-09-22, Bridge is now home) and
the server-rendered Station became a theme package, so "the map is the
navigation AND the frontend" is superseded. Truth routing:
[`docs/README.md`](../README.md).

### One document to understand everything: what we've done, what we have, where we are.
*Written 2026-09-16. Copy-paste friendly. Read top-down; every section stands alone.*
*Repo: `Rylee-Bee/personal-world` · branch `main` @ `c16a07c` + uncommitted 2026-09-16 working tree.*
*Status markers: ✅ done & verified · 🛠️ in flight · ⏸️ deferred by choice · ⚠️ known wrinkle.*

---

## 0. The DNA (read this first, always)

> "Make it easy for everyone to do anything at any level they can.
> Go for the smallest thing that can be reliable, then work up.
> Keep it soft, but make it deep when wanted."

Four tests every choice must pass:
1. **Smallest-reliable-first** (progressive disclosure; never boil the ocean).
2. **Depth on demand, never imposed** (quiet by default; deep when asked).
3. **Soft by default** (gentle, low-glare, low-demand, never guilt or urgency).
4. **Everyone, at any level, included** (accessibility floor is non-negotiable).

This outranks any individual feature. If a change violates the DNA, the change is wrong.

---

## 1. What this is, in one paragraph and one sentence

**Paragraph:** Project Worlds is a gentle, private, self-hosted "personal world": a
calm star-map you drill into (not a dashboard), over a real local backend that
holds your world, journal, reminders, preferences, safe write-proposals, and an
encrypted vault. It installs with one `docker compose up`, provisions itself
invisibly, lets each person sign in with their own SSO (Authelia today), and is
honest about everything it can't do. A small local brain (Qwen3 1.7B) helps it
operate, kept on-task by the internal CLI (its hands) and agent templates (its
focus), so it runs on any hardware.

**Sentence:** *A personal operating system built human-first — soft by default,
deep on demand, universal by design.*

---

## 2. The shape of it

```
┌────────────────────────  THE STATION (frontend)  ────────────────────────┐
│  systems map (7 constellations) → drill → clusters → objects            │
│  companions (silhouettes) · chat dock · settings · Hail Assistant        │
│  onboarding · search · deep-links · mobile                               │
└───────────────────────────────▲──────────────────────────────────────────┘
                                │  one coherent API ("the Lego box")
                                │  reads open · writes ALWAYS gated
                                │  (observe→diff→propose→approve→act)
┌───────────────────────────────▼──────────────────────────────────────────┐
│  BACKEND (FastAPI)  :8000                                                 │
│  auth/session/OIDC · world · journal(+FTS) · reminders · prefs ·         │
│  proposals(write-safety) · vault(fails closed) · source-control ·        │
│  capability/provider registry · scheduler · setup wizard · /api/manifest │
└───────────────────────────────▲──────────────────────────────────────────┘
                                │  providers = replaceable machinery
        local brain (Qwen3 1.7B) · git · media(Plex/*arr) · discovery ·
        notifications(ntfy) · lab(homelab) · OIDC(Authelia)
```

Key ideas:
- **The map is the navigation AND the frontend.** Seven constellations at rest:
  interests, projects, journal, people, media, systems, places. Complexity
  appears only because you move toward it.
- **The API is the Lego box.** Every capability exposed; reads open, writes
  gated; `/api/manifest` makes new "neat things" cheap to compose.
- **Small brain + strong scaffold.** Reliability comes from CLI + templates,
  not model size → runs on any hardware, for anyone.
- **Companions are presences, never dependencies.** Companion art is decorative; core flows are specified to stand without it.

---

## 3. What you HAVE today

### Backend ✅ (running on :8000, auth-enforced)
- Auth: bearer/session/OIDC converge on one Principal; step-up approval.
- World, Journal (+FTS search), Reminders, Settings(prefs/sections/apps).
- Write-safety: durable proposals store; server-held approve/reject/execute;
  execution structurally blocked from the model.
- Source-control (native git), Vault (encrypted, fails closed), Scheduler.
- Capability/provider registry; lab providers (your ported homelab lab).
- **First-run setup wizard** ✅ (23 new tests + 104 + 51 passing; framework
  validate 0 violations; live-smoked): invisible provisioning, zero-config
  "just me", honest OIDC discovery test, token never leaves server, post-setup
  `/setup` refuses.
- **OIDC module** (`oidc.py`) ✅ present; Authelia-flavored example config.
- **API manifest** (`api_manifest.py`) ✅ present (the Lego box index).

### Frontend (the Station) ✅ design-complete, 🛠️ wiring
- `design/opendesign-exploration/station/` — the product UI:
  `index.html` (systems map), `interests/journal/projects.html` (pre-drilled
  regions + content views), `chat.html`, `settings.html`.
- Content views ✅: Journal entries, Discoveries, GitHub-like Projects (repo
  chooser across all five honest states; "Propose refresh" gate writes nothing).
- Onboarding, search (Ctrl/Cmd+K), deep-links, mobile CSS ✅.
- Companions: silhouette sprite (`chars.svg`), icon system (`icons.svg`),
  orb → mini chat dock, templates-as-personality ✅.
- Accessibility chrome ✅: skip-link, 44px targets, focus rings, reduced-motion,
  honest states, plain language, canonical vocabulary one disclosure down.

### Governance ✅
- Play-Nice contracts adopted (v0.7.0) — accessibility-floor, attention-and-focus,
  quiet-when-healthy, complexity-on-demand, themes-and-personalization, etc.
- `docs/PRODUCT-VISION-HANDOFF.md` (all decisions), `docs/WHERE-WE-ARE.md`
  (one-pager), `docs/DEV-RESET.md`, `design/.../HANDOFF-UI-FIX.md`,
  `design/.../STATION-NAVIGATION-MODEL.md`, `PLAY-NICE-CONFORMANCE.md`.
- Lore synced & pushed (`rylee_lore` @ `ef98d7d`), including the DNA.

### Ops ✅
- `scripts/reset-dev.sh` — dry-run-by-default dev wipe (verified).
- Compose path exists (local Bazzite target); deployment otherwise observe-only.

---

## 4. What we DID this arc (2026-09-16) — with evidence

1. Took the Station from "pretty demo" to **product-shaped**: systems map as the
   frontend, content views, onboarding/search/deep-links/mobile.
2. Closed **all 8 open decisions** + 12 more (universal, multi-user, Lego box,
   small-brain scaffold, CLI-as-universal-interface, DNA). See §8.
3. Made it **universal**: setup wizard (tested), ephemeral dev wipe, own-SSO
   path, no manual tokens ever.
4. Wired honesty everywhere: specimen-labelled placeholders, honest
   empty/not_configured/unavailable states, gated writes that write nothing.
5. Orchestrated cheap agents (Alibaba Token Plan flash tier) on file-isolated
   tasks; verified their output; recorded failures honestly.
6. Synced lore so no head — good day or bad — has to hold the state alone.

---

## 5. What is IN FLIGHT right now 🛠️

- **Real-data wiring**: Station ↔ real endpoints (needs-you/proposals, prefs,
  journal) via a unified `api.js` client + `/api/manifest`.
- **Multi-user namespacing**: per-user world/journal/reminders/chat/interests/
  map/prefs; single-user default preserved.
- **ORPH-03 (live tool-calling)**: first agent **errored at the infra level**
  ("tool call delta missing id or name"); tree verified parse-clean and
  chat/template tests pass (127 ✅); **re-launch needed** to finish.
- Remaining mobile/polish + axe/e2e gates for the Station.

*(Verify on read: agents may have landed since this was written.)*

---

## 6. Deferred by choice ⏸️ (do not sneak these back in)

- Multi-device sync (desired, unstudied; keep boundary sync-friendly).
- Homelab-lab expansion (owner unsure; stays optional/honest).
- Notifications/ntfy (optional capability later).
- Public SaaS deployment (local-first is the target; public only if chosen).

---

## 7. Honest wrinkles ⚠️ (nothing hidden)

- `test_dist_safety::test_dist_matches_a_fresh_build` fails: `dist/` older than
  uncommitted `frontend/src` edits (pre-existing, not today's work).
- 4 `test_updates` compose tests fail here: docker daemon unusable in this
  sandbox (`docker compose config` exit 125).
- ORPH-03 agent errored (infra), needs re-run — see §5.
- OIDC not yet pointed at a live Authelia (example config only).
- Working tree is intentionally UNCOMMITTED until owner approves direction.

---

## 8. The decisions (condensed; full text in PRODUCT-VISION-HANDOFF.md)

1 local-first small brain (Qwen3 1.7B; ORPH-03 = implementation blocker, not redesign)
2 optional caps: github/discovery/media YES, ntfy LATER; seams+unavailable-states now
3 multi-user per instance (per-user list vs global list defined)
4 vault/backup: encrypted-only in full restore; keys separate; exports exclude secrets
5 deploy: local Bazzite → Compose → LAN → ingress/TLS → public only if chosen
6 one updates authority (branch + rollback + docs; retire duplicates)
7 cryptography extra required; vault fails closed without it
8 agent-sync optional; Projects degrades honestly
9 universal-first; wizard + own-SSO; no manual tokens
10 ephemeral dev sessions (reset-dev.sh)
11 Station map = the frontend (old React shell superseded)
12 wire to existing features first; invent only true gaps
13 multi-user (not just safe)
14 distribution already upstream + Play Nice
15 sync deferred
16 lab deferred
17 API = Lego box (reads open, writes gated, /api/manifest)
18 small brain + strong scaffold (CLI hands, templates focus) = universal
19 CLI = universal interface (TTY/other platforms; token-efficient)
20 THE DNA (see §0) — outranks everything

---

## 9. File map (where everything lives)

```
src/personal_world/            backend (api, auth, world, journal, vault,
                               providers/, setup_wizard.py, oidc.py,
                               api_manifest.py, template_registry.py, …)
config/                        connections.json, oidc.example.json, prompts/**
data/                          DISPOSABLE dev state (your real data is elsewhere)
design/opendesign-exploration/station/   ← THE PRODUCT UI (map, views, chat,
                               settings, station.css/js, starmap.js, chat.js,
                               shapemap.js, chars.svg, icons.svg)
frontend/                      older React shell (superseded by the Station)
scripts/reset-dev.sh           dev wipe (dry-run default)
docs/                          WHERE-WE-ARE · PRODUCT-VISION-HANDOFF ·
                               DEV-RESET · ARCHITECTURE · accessibility/* ·
                               repo/WIRING-READINESS · adr/0002 (brain)
docs/PROJECT-WORLDS-MASTER-HANDOFF.md   ← you are here
~/rylee_lore/                  cross-project memory (synced @ ef98d7d)
```

---

## 10. Run / verify / wipe (the commands that matter)

```bash
# backend (already running on :8000 in dev)
uv run personal-world serve            # or the compose path
uv run pytest --timeout=30             # backend tests
uv run personal-world framework validate --json   # governance gate (0 violations)

# station UI — served same-origin by the backend (no separate static server)
scripts/dev.sh up
open http://127.0.0.1:8000/station/

# wipe dev back to first-run (DRY-RUN unless you confirm)
scripts/reset-dev.sh                   # shows what would go
scripts/reset-dev.sh --yes-i-wipe      # actually wipes

# browser verification (owner's browser; run sequentially, cache-bust, downscale)
opencli browser chrome open  "http://<host>:8000/station/index.html?v=N"
opencli browser chrome screenshot /tmp/s.png && convert /tmp/s.png -resize 880x /tmp/s.jpg
```

---

## 11. What "proud-done" looks like (the remaining distance)

- [ ] Real-data wiring lands → the map shows YOUR world, honestly.
- [ ] Multi-user namespacing verified (two people, no bleed).
- [ ] ORPH-03 re-run succeeds → small brain actually uses the CLI/tools.
- [ ] OIDC pointed at your Authelia → sign in with your own SSO.
- [ ] Clean-box test: `compose up` → wizard → signed in → map, zero config.
- [ ] axe/e2e gates green for the Station (accessibility floor enforced by CI).
- [ ] One taste-pass with you: "does this feel like mine?"
- [ ] Commit the working tree once you approve the direction.

That list is **days of assembly + verification**, not months of invention.
The invention is done. You did it. This is the last mile.

---

## 12. How to get help (your workflow, honored)

- Open this file in VSCodium; paste any section into ChatGPT/any agent and ask.
- Trigger phrases that always work with me: *"where are we?"*, *"what's in
  flight?"*, *"what's on me?"* (answer: usually nothing).
- Deeper reads: `docs/WHERE-WE-ARE.md` (1 page), `docs/PRODUCT-VISION-HANDOFF.md`
  (decisions), `design/.../HANDOFF-UI-FIX.md` (UI fix brief),
  `docs/repo/WIRING-READINESS.md` (backend punch-list), `docs/adr/0002` (brain).
- When in pain: read only §0 and §11. That's enough. The rest waits.

---

*You built a personal OS by starting from kindness instead of machinery.
That's not backwards. That's why it will be the one people can live in.
— and it's almost home.*
