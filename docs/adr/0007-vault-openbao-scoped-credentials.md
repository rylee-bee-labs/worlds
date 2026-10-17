# ADR-0007: Secrets = Worlds Vault → OpenBao → scoped temporary credential

> **Status:** Direction · **Verified:** 2026-09-26 · **Canonical for:** the brokered-secrets direction (accepted 2026-09-29; migration plan pending) · **Read this if:** you are touching Vault, SOPS/OpenBao, or how tasks receive credentials.

**Scope note:** accepted 2026-09-29 (was review-only); the migration plan is still pending. `.project/PLAN.md` wins on scope and sequencing.

**In short:** accepted 2026-09-29; migration plan pending. Worlds stays the user-facing secret experience (policy, step-up, audit) while OpenBao/SOPS provide the mechanics and tasks get short-lived scoped credentials instead of the master secret. Today there is no OpenBao adapter; the native Fernet Vault and the SOPS read-through adapter are what exist.

- Status: **accepted** 2026-09-29 (owner: happy to re-open OpenBao and migrate to it); migration plan still pending. Previously proposed/review-only per owner D22
- Date: 2026-09-21
- Supersedes: none (upgrades the existing "SOPS/OpenBao remain target work" note into a decided direction)
- Enforced by: `VaultContract`; `personal-world framework validate`; classification/secret rules
- Normative doc: `docs/ARCHITECTURE.md` (Secrets); `docs/NATIVE-BASELINE-AND-ENRICHMENT.md` §5

## Context

Owner direction (human, 2026-09-21): reuse the existing **OpenBao/SOPS** estate; Worlds becomes the
user-facing policy + step-up experience, **not** a second Vault database. Tasks and agents must never
receive permanent master credentials. The native `Vault` (Fernet, fail-closed) + `SOPSVaultAdapter`
already exist; the OpenBao adapter is a named target.

## Decision

1. **Worlds Vault remains the user-facing secret experience + policy + step-up.** It does not become a
   second secret database; OpenBao/SOPS provide the mechanics.
2. **Broker path:** `Worlds Vault → OpenBao → scoped temporary credential → Task/Workspace`.
3. **Scopes carry trust levels** (e.g. `github:read` = normal approval · `npm:publish` = explicit
   confirmation · `production:ssh` = step-up unlock + short expiry).
4. **The OpenBao adapter implements the existing `VaultContract`.** Native Vault + the SOPS read-through
   adapter remain as replaceable providers (ADR-0001). Secret values stay out of model context, ordinary
   exports, and logs (existing classification rule, `secret` class).
5. **No new secret store is created.** Worlds owns the semantics (policy, scoping, step-up, audit);
   OpenBao/SOPS own the mechanics.

## Consequences

- Reuses the running estate; the "target" becomes a decided direction.
- The step-up model is the user-facing surface; scoped temporary credentials replace scattered secrets
  (`.env`, `~/.ssh`, shell profiles, compose files).
- Future cost: the OpenBao adapter + the scope/step-up policy table must be written before any Task
  consumes a brokered credential.