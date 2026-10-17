# Project Worlds — Unknowns Handoff (2026-09-17)

**Repo state:** `Rylee-Bee/personal-world` `main @ 2a1f3e1`, pushed, gates green
(backend pytest green w/ unavoidable skips, Playwright 25/1-skip, `framework
validate` 0 violations). Only the dirty files listed in §1 remain. The alpha-remediation pass (merged via `2d530be`) plus two earlier runs (`cccd988` hardening/swarm, `2a1f3e1` UIX batch) are all on remote.

## 1. IDENTITY-LANE WIP — no brief exists (the thing I don't know)
Working tree has 3 dirty files **no handoff owns**:
- `src/personal_world/identity.py`
- `src/personal_world/providers/adapters.py`
- `tests/test_identity.py`

Uncommitted, unparked, unexplained. Next agent: `git diff` all three, decide
with the owner: (a) finish to green and commit, or (b) `git restore` discard.
Do not sweep into any other commit (standing rule). If (a), the identity-scope
work overlaps swarm-deferred item "agent scopes" — check
`.project/HANDOFF-SWARM-IMPROVEMENTS-2026-09-16.md` for the named deferral
reason before designing.

## 2. Owner product decisions — UX lane's five "too big for me" items
All verified against live app (:8731 fixture) — the code sites are known, the
decisions are liking/taste, not mechanical:
- **UX-01 chat wiring** — chat room is currently a dead room; per-send it
  injects a dev-note "system" line. Wire to the real chat capability (API-010,
  registry exists in `chat_registry.py`, but all providers post `stream:
  False`). Decide: wire local-only (privacy-consistent) or provider-mediated.
- **UX-02/03 journal consolidation** — three competing journal surfaces (real
  API-005 panel + stale specimen panel + localStorage panel). Keep API-005,
  delete the impostors. Decide whether the localStorage "device notes" stay as
  a clearly-labelled separate surface (UX-16 already relabelled it).
- **UX-04 settings binding** — controls write localStorage only; real prefs
  API exists (`PUT /api/prefs`, API-030/031). Decide bind-now vs honest label.
- **UX-10 projects wiring** — page is specimen git-dump of 5 fake repos; real
  endpoints refute wiring (API-079/033/034). Decide wiring or "marked
  specimen" only.
- **UX-09 mechanical** — low-demand mode renders dual Needs-you panels; hide
  the full mount under quiet state. Cleared as mechanical, not in last batch.

## 3. Documented-but-unverified gaps (from the security hardening wave)
- **Step-up proxy secret** must be documented before an operator relies on
  header delegation: the env var name, the proxy expectation, and the
  fail-closed behavior. Where to write it: `docs/oidc.md` (or a dedicated
  ops doc) + `.env.example`.
- **GHCR retention**: the Gitea toolbox-publish port has no GHCR version
  prune; retention must be configured in GitHub package settings (one-time UI
  action, not code).

## 5. Resolution note — 2026-09-17 language pass (appended; §1–§4 above are historical)

§2's five owner items resolved as follows (verify against the manifest
`design/handoff/owner/language/LANGUAGE-IMPLEMENTATION-MANIFEST.md`):
**UX-01** chat wired to real `POST /api/chat` with honest states;
**UX-02/03** the journal's specimen panel is unmounted (`data-unused`)
— the normal route shows the real API-005 journal, and the localStorage
panel survived as the clearly-labelled "Notes on this device" surface;
**UX-04** resolved as "honest label": the Settings preferences table
names the two scopes per row ("This browser · Your Project Worlds
account", not synchronized) instead of silently binding;
**UX-10** projects/page wired to real source-control read with honest
states; **UX-09** fixed (single Needs-you panel under low demand).
§1's identity-lane WIP was committed in `1d725c6` (fail-closed corrupt
users.json). §3's step-up proxy-secret documentation gap (`PW_PROXY_STEPUP_SECRET`
env var + proxy expectation + fail-closed behavior) is **still open** —
not in `env.example` nor `docs/oidc.md`; owner/ops to document before
relying on header delegation.

## 4. Standing operating notes
- Fixture for any live walkthrough: `node frontend/e2e/server.mjs` → :8731,
  seeded world, token `ci-token` (kill after; don't test against :8000 — its
  token is stale pre-identity-lane).
- `tests/test_public_safety.py` now scans ALL tracked text for: dns/rug1918
  octet regex, `duckdns`, and the personal absolute path patterns defined in
  the gate's `PERSONAL_PATH_EXEMPT` block (never quote them in docs — this
  handoff itself tripped the scanner once). Synthetic literals in tests carry `pw-safety:
  synthetic` on the same line. Historical evidence files are deliberately
  exempted (3 dated 2026-09-12 attestation files + `compose.homelab.yaml`).
- Never push from the dev box via hooks path without `git-lfs` installed and
  skip claims of LFS content (pre-push hook hard-fails locally otherwise).
- If tests fail on `test_torture.py`-style network-suite items, that's forge
  infra absence, not your change — check the stash-repro pattern before
  blaming a commit.

## Alpha status
`READY-FOR-PRIVATE-TECHNICAL-ALPHA` contingent on the owner running
`docs/ALPHA-ACCEPTANCE.md` (evidenced OUTSIDE the repo). Public-facing
alpha needs its own review — not authorized by any current handoff.
