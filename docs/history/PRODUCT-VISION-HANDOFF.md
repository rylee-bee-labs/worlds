# PRODUCT VISION — my reflection, for Rylee to confirm or correct

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [`.project/CURRENT.md`](../../.project/CURRENT.md)) · **Read this if:** you want the dated 2026-09-16 vision write-up and its decision list for provenance · **Superseded by:** [`.project/PLAN.md`](../../.project/PLAN.md) for direction and [`.project/CURRENT.md`](../../.project/CURRENT.md) for state.

**In short:** the agent's 2026-09-16 write-back of what it thought
Worlds was, plus the decisions closed that day. Since it was written, the
interface flipped to the React rebuild in `ui/` (2026-09-22, Bridge is now
home) and the server-rendered Station became a theme package; decision 12
("the Station map IS the frontend") is superseded. Truth routing:
[`docs/README.md`](../README.md).

**Written 2026-09-16 by the agent, from the repo + our conversations.**
This is *my* model of what you're building, written back to you so you can
answer honestly and fix wherever I'm wrong. It is not authoritative until you
say so. Where I'm uncertain I say so.

---

## The need (why this exists)

You need **a place to keep your thoughts and your life organized** that is
*gentle by construction*: it must respect low-energy days, motion sensitivity,
attention limits, and cognitive fog — because you live with those, and because
the people you'd trust with a tool like this do too. Mainstream productivity
software is built for a high-energy, notification-tolerant, mouse-first user
and then punishes everyone else. Nothing mainstream offers "quiet when
healthy," "low-demand mode," or "never tell me how to feel."

You also need it to be **settable-up by someone who doesn't know computers** —
which is why it must install as **one Docker Compose command**, auto-provision
its own auth, and never make a human paste a token or edit config by hand.

**And it must be UNIVERSAL before it is personal.** You are deliberately
building it for *anyone* first; your own data stays out until you trust it
(your real data lives in a separate data repo, not here). Dev sessions are
**ephemeral** — wipe-able back to a clean first-run. A real user's on-ramp is a
**setup wizard** that provisions invisibly and then helps them tie it to
**their own SSO** (yours is **Authelia**; the implementation is generic OIDC).
Git/GitHub is the time machine for code; `data/` is disposable.

And you need to **know it's real and durable**: your data persists, is private,
is backup-able, and the tool is honest about what it can and can't do.

## The product (what it is)

**Project Worlds / Personal Worlds** — a local-first personal world:

- **One backend:** FastAPI + a capability/provider registry + durable local
  stores (world, journal, reminders, prefs, proposals, vault). Providers are
  replaceable machinery; your data is the durable truth.
- **One frontend:** the **Station** — a calm, sci-fi, accessible UI whose core
  is a **semantic systems map** (seven constellations: interests, projects,
  journal, people, media, systems, places) you drill into, rather than a
  dashboard or a wall of screens.
- **One capability model:** every external thing (brain, media, discovery,
  source-control, lab, notifications) is a capability with an honest status
  (healthy / needs you / not set up / unavailable / stale / unknown).
- **Local-first brain:** a small local model (ADR 0002: Qwen3 1.7B, LFM2.5
  fallback) that helps operate the world but never *is* the world and never
  writes authoritative facts. Remote brain = optional later provider.
- **Companions** (Mermaid, Ratatoskr, Robot, Burrito) as gentle silhouette
  presences + chat personalities — presentation, never dependency.
- **Governance:** your **Play Nice contracts** (accessibility-floor,
  attention-and-focus, quiet-when-healthy, complexity-on-demand, etc.) are the
  product's quality bar and bind every agent that touches it.

## The vision, in one sentence

> A local-first, gentle, radically accessible personal world that keeps your
> thoughts and life organized behind a calm semantic map, installs with one
> `docker compose up`, auto-provisions its own auth, keeps your data durable
> and private, expands to your homelab "lab," and stays honest about everything
> it can't do.

## Current state (verified this session)

**Built & running:** authenticated backend on :8000 (401-enforced), world,
journal (+FTS), reminders, settings, write-safe proposals, native git reads,
vault (fails closed), scheduler, lab providers (`providers/lab_*.py`,
`native_lab.py` — your ported homelab lab), lifecycle.
**Your real data already exists:** `data/journal.ndjson`, `data/world.json`,
`data/memory.fts5.db`, `data/sessions.json`; first-run already generated
`data/.env → PW_API_TOKEN` and `setup-complete`.
**Partial:** provider-registry convergence, proposals review UI, chat
(no stream/history; tool-calling = ORPH-03), frontend defects (Projects health,
Today journal), storage/backup boundary, vault step-up.
**Not configured:** OIDC (only `oidc.example.json`), media/discovery/ntfy/gh
(optional capabilities), deployment apply (observe-only).
**Frontend:** the Station design prototype (this repo's
`design/opendesign-exploration/station/`) is coherent and close; the older
React frontend at `frontend/` is the current product shell. **Convergence
question below.**

## Decisions now CLOSED (yours, 2026-09-16)

1. Brain: local-first, Qwen3 1.7B intent (ADR 0002 stands); ORPH-03 is an
   implementation blocker, not a redesign; chat reports unavailable honestly
   until then; no fake replies; remote fallback optional later.
2. Optional caps: YES github/source-control, discovery/search, media/*arr;
   LATER ntfy/webhooks. Build seams + unavailable states now; don't block on
   secrets (you'll add via Vault).
3. Identity: single-user first, multi-user-safe architecture; per-user =
   world/journal/reminders/chat/interests/map/prefs/personal connections+creds;
   global = app config, capability catalog, system health, deployment.
4. Vault/backup: full-restore may include `vault.enc` **encrypted only**;
   keys/recovery separate; ordinary exports exclude secrets; fail closed.
5. Deployment: local Bazzite via existing Compose path → LAN → existing
   ingress/TLS when appropriate → public only if explicitly chosen later.
6. Updates: consolidate to one authority; may edit tracked compose.yaml on a
   branch with rollback + docs; retire duplicates.
7. Cryptography extra: yes, required; vault stays fail-closed without it.
8. agent-sync: optional; Projects degrades honestly without it.
**Plus (this session):** non-technical setup is a first-class requirement →
Compose is the install path and first-run must auto-provision auth.
9. **UNIVERSAL FIRST:** build for anyone; your own data stays out until you
   trust it (it lives in a separate data repo). Existing `data/` is
   experimental and disposable.
10. **EPHEMERAL DEV:** sessions wipe back to a clean first-run via
    `scripts/reset-dev.sh` (dry-run by default; see `docs/DEV-RESET.md`).
11. **ON-RAMP:** a first-run **setup wizard** provisions invisibly
    (token / stores / FTS) and then offers local-token (zero-config) or
    your-own-SSO via **generic OIDC**, with **Authelia** as the reference
    provider. No human ever pastes a token.

## What "done" now means (my read)

- `docker compose up` on a fresh box → boots backend + frontend, generates its
  own token/session, shows the Station, and works with zero config.
- The Station talks to the REAL backend (auth session, prefs, proposals/
  needs-you, FTS search, journal/interests/projects data) with honest states.
- Real chat once ORPH-03 is fixed; honest "unavailable" until then.
- Lab expands as a first-class capability surface.
- Backup/restore boundary honored; your existing data preserved/imported.

## Open questions — answer honestly, correct me

1. **Frontend convergence:** is the Station systems-map UI the *future*
   frontend (React rebuilt around it), or does the existing React shell stay
   and merely adopt the map? This decides where all remaining UI wiring lands.
2. **Per-instance identity model:** with Authelia as SSO, does one instance
   serve ONE person (single-user, simplest) or a household (multi-user now)?
   Your decision #3 says single-user-first / multi-user-safe; confirm whether
   Authelia-backed multi-user should move sooner.
3. **Lab scope & priority:** what should the homelab lab grow into
   (inventory / health / deploy / secrets as a first-class constellation), and
   how high vs core wiring?
4. **Distribution:** what does "push it out" mean concretely — public repo +
   releases + a quickstart docs site? License? This shapes wizard copy and the
   compose quickstart.
5. **Multi-device:** one box per person forever, or eventual sync between a
   person's devices? (Changes storage/identity urgency later, not now.)

**Answered already (no longer open):** non-technical user = anyone (universal);
OIDC = real, Authelia now; existing `data/` = disposable/experimental with your
real data in a separate repo.

## Round-2 answers (2026-09-16) — now decisions

12. **The Station map IS the frontend.** Wire it to features that already
    exist; invent only where a feature is genuinely missing. Lean on agent
    templates + simple settings rather than bespoke screens where possible.
    (This closes the convergence question: the old React shell is superseded
    by the Station as the product UI.)
13. **MULTI-USER, not just multi-user-safe.** One instance can serve multiple
    people (Authelia identities). Per-user: world, journal, reminders, chat/
    history, interests, map structure, prefs, personal connections/creds.
    Global: app config, capability catalog, system health, deployment.
14. **Distribution:** already lives in the upstream public repo together with
    the Play Nice contracts. No new distribution machinery needed now.
15. **Multi-device sync:** desired but **deferred** (not yet studied; must stay
    easy; possibly an app via sync later). Keep the storage/identity boundary
    sync-friendly; do not build sync now.
16. **Lab scope:** deferred / unknown by choice. Lab remains an optional,
    honest capability; revisit only when the owner cares.
17. **THE API IS THE LEGO BOX.** Every backend capability is exposed to the
    Station / agent templates / settings as ONE coherent, discoverable surface:
    all **reads** broadly available; all **writes** available but **always
    gated** (observe → diff → propose → approve → act, step-up). Serve a
    machine-readable **API manifest** so new features compose without new
    backend work. Never unrestricted mutation. This is why "every piece has
    every api call available" — it's what makes neat things cheap to build.
18. **SMALL BRAIN + STRONG SCAFFOLD = UNIVERSAL.** The local small model
    (ADR 0002: Qwen3 1.7B) is kept on-task by two rails: the **internal CLI /
    tool registry** as its hands (contract-bound commands) and **agent
    templates** as its focus (structured prompts per surface/companion).
    Reliability comes from the scaffold, not model size — which is what lets
    this run for anyone on any hardware. Therefore **ORPH-03 (live
    tool-calling) and first-class, editable templates are CORE**, not optional.
    Templates + tool schemas must stay simple/robust for a 1.7B model and
    parse leniently when the model emits imperfect tool syntax.
19. **CLI = THE UNIVERSAL INTERFACE.** A real CLI lets anyone wire Project
    Worlds into a TTY or any other platform, and is the most token-efficient
    surface for a small agent — more people, more platforms, cheaper models.
    (Aligns with play-nice interfaces: cli, human-and-machine-parity,
    machine-readable-output.)
22. **CLI↔API PARITY, EVERY ACTION WRAPPED.** Everything the product can do
    has a simple CLI wrapper AND an API route, both derived from the SAME
    manifest so they never diverge. `personal-world manifest` is the bot's map;
    `personal-world api <METHOD> <path>` is the generic escape hatch; friendly
    one-verb wrappers cover every capability. Writes PROPOSE by default and
    need explicit `--approve` + step-up; reads need nothing. JSON envelope +
    honest exit codes so small agents "just file things the right way."
20. **THE DNA (north star, outranks any feature):** "Make it easy for everyone
    to do anything at any level they can. Go for the smallest thing that can
    be reliable, then work up. Keep it soft, but make it deep when wanted."
    Smallest-reliable-first · depth-on-demand-never-imposed · soft-by-default ·
    everyone-at-any-level-included.
21. **VISION: built-in updates for content packs** (owner's "ideal world").
    Theme packs, persona/template packs, companion packs, and interest presets
    should update in-product. Anchors already exist: `theme_pack.py`,
    `template_registry` + `config/prompts`, API-065 themes, WORLD-007 packs,
    discovery interests. Required shape when built: opt-in, provenance-bearing
    (signed) pack channel that delivers updates through the SAME write-safety
    gate (observe→propose→approve), never silent mutation; uninstallable;
    never a dependency for core function. Deferred until the runtime is boring.

## What's on YOU (tiny, by design)

- Nothing blocking. Compose + first-run auto-provision removes the token step.
- Later, optionally: point OIDC at a real IdP; add optional-capability secrets
  via Vault; answer the six questions above when you have spoons.

*Everything else is wiring we can finish without you.*
