# Native Baseline and Optional Enrichment

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the native-baseline / optional-enrichment framework invariants (capability ownership, provider modes, enforced rules) · **Read this if:** you are adding a capability or provider, or checking what may become a hidden dependency.

**In short:** Worlds must stay usable with zero optional integrations; external systems may enrich a capability but never define or gate it. This page is the normative framework contract — its invariants are enforced by `personal-world framework validate` and `tests/test_framework.py`.

> **Superseded by [ADR-0008](adr/0008-front-door.md) for front-door providers:** the capability registry and provider-mode rules below are retired; the gate now validates C1 config, secret references, recipes, the zero-provider baseline, compose additivity and Memory exports. See [`docs/rebuild/FRAMEWORK-GATE.md`](rebuild/FRAMEWORK-GATE.md) for the old-rule mapping.

## 1. The principle

> **Native baseline. Optional enrichment. No mandatory ecosystem
> dependency.**

Worlds is a standalone OSS product (formerly "Personal World", then
"Worlds"; technical identifiers unchanged) with its own CLI, API, and
dashboard. External systems — Gitea, GitHub, Forgejo, Traefik, Komodo,
OpenWebUI, Home Assistant, candy-dispenser, model runtimes, Figma —
may enrich it. None may become a hidden requirement.

**Stable truth. Replaceable machinery.** A provider may increase
fidelity, automation, or convenience. It may not redefine the user's
capability. The core must survive the disappearance of every optional
integration. If swapping Gitea for GitHub, or Traefik for Caddy, feels
like surgery, the boundary is wrong.

## 2. Capability ownership (the core invariant)

> A capability belongs to Worlds.
> A provider implements or enriches that capability.
> The provider does not define the capability.

```text
USER-FACING CONCEPT
        ↓
STABLE CAPABILITY CONTRACT        (core-owned: source_control)
        ↓
NATIVE / BASIC IMPLEMENTATION     (if any: repo metadata, links)
        ↓
OPTIONAL ENRICHMENT PROVIDERS     (github, fake; forge adapters exist
                                   as substitution-proof machinery)
        ↓
SPECIALIST PROVIDER UI            (the provider's own web UI, for deep work)
```

The failure mode this forbids: `source_control == Gitea`, so removing
Gitea removes the *concept* of source control from the world.

## 3. Layering and provider modes

`ProviderMode` (`src/personal_world/model.py`) is the closed
vocabulary:

| Mode | Meaning | Absence |
|---|---|---|
| `native` | Core-owned baseline; ships with the OSS product | n/a — it ships |
| `enrichment` | Optional third-party richness (the default) | capability degrades gracefully, never breaks |
| `replacement` | Swaps the native baseline for another system | still substitutable like any provider |

Separately, availability is always reported, never silent:
`healthy / warning / unknown / needs_attention / unavailable / stale /
disabled / not_configured` (`src/personal_world/status.py`). Absence
of a provider is reported as `not_configured`; a dead provider as
`unavailable`; a reachable but degraded provider may report `warning`
or `needs_attention`. `unhealthy` is not a canonical status. Old observations are never re-shown as
current (`World.stale_capabilities`).

## 4. Rules (enforced)

Each rule cites its enforcement path.

| # | Rule | Enforced by |
|---|---|---|
| 1 | Core-only must work: `docker compose up -d` yields a healthy core with zero providers | `TestCoreOnly`, CI compose job |
| 2 | Native baseline: major capabilities have useful local meaning without third parties, or an explicit `not_configured` state | `STANDARD_CAPABILITIES` native flags, manifest |
| 3 | Optional enrichment: providers declare mode against a closed vocabulary | `validate_connections` provider-mode check |
| 4 | Provider removal is safe: no corruption, baseline remains, fidelity degrades visibly | `TestProviderLifecycle` |
| 5 | Provider failure is not core failure: unrelated capabilities unaffected | `TestProviderLifecycle.test_provider_unavailable_...` |
| 6 | Providers cannot become required without anyone deciding it: no hidden boot deps, required = explicit + justified | `validate_compose_file`, `validate_connections` optional-default check |
| 7 | User-facing meaning is provider-neutral: semantic vocabulary, not vendor shape | manifest key test, capability contracts |
| 8 | Provider-specific data is namespaced: generic state portable, details optional | capability contracts return semantic `data`; vendor fields never canonical |
| 9 | Provider-specific actions do not pollute core actions | generic action set only; deep work hands off to provider UI |
| 10 | Specialist UIs remain valid escape hatches: deep links optional metadata | `deep_links` in provider config (optional) |
| 11 | Compose is additive: core + N providers works for any N, removal of one requires no rebuild | `validate_compose_file`, compose profiles |
| 12 | Init/bootstrap needs no providers: fresh install usable immediately | `init_world`, `TestInit` |

## 5. Provider registration contract

`config/connections.json` is the integration surface. A connection:

```json
{
  "type": "http_status",
  "name": "example-probe",
  "capability": "deployment",
  "mode": "enrichment",
  "required": false,
  "required_reason": null,
  "url": "http://service.example.invalid"
}

GitHub source-control enrichment needs no connection entry at all:
it rides the authenticated `gh` CLI session on the host
(`providers/github.py`, read-only) and degrades to the native local-git
baseline when gh is absent.
```

- `type` maps to an adapter in `build_registry` (unknown types are
  skipped, not fatal — a standalone deployment boots with zero
  providers connected).
- `name` must be unique (duplicate IDs are a validation violation).
- `capability` must be a declared capability (claiming an undeclared
  capability is a violation: capabilities are core-owned).
- `mode` defaults to `enrichment`; only the closed vocabulary is valid.
- `required: true` is an **explicit, rare, justified exception** and
  requires `required_reason`. Optional is the default.

### Secret rule

Registration never contains inline secrets. Secret material is
referenced symbolically (`token_env`, `api_key_env`, `secret_ref`) and
resolved through env indirection at the adapter or a secret-management
boundary. `SopsBroker` pipes values to consumers; native `Vault` and the
read-through `SOPSVaultAdapter` expose the `VaultContract` operations.
The HTTP Vault currently instantiates native `Vault` directly; configurable
backend substitution and an OpenBao adapter remain target work. Secret values
must stay out of ordinary exports, logs, and model context. See
[Architecture](ARCHITECTURE.md#secrets-current-implementation-and-target)
for current retrieval restrictions and encryption limitations.
The validator rejects keys that
look like inline secret material (`token`, `password`, `api_key`
values) — only the `_env`/`_ref` indirection forms are allowed.

## 6. Classification and policy rules

Provider observations must carry or inherit data classification
(`world / private / secret`, `src/personal_world/classification.py`).
A provider cannot bypass classification by supplying data — the core
assigns classification when recording facts, and the payload's
self-declared class is ignored (`TestProviderClassificationGuard`).

Optional providers do not weaken policy. Provider output passes
through core policy enforcement; cemented policies reject every
non-user mutation path (`tests/test_core.py::TestCementedPolicy`).

## 7. Export rules

- **settings-export** expresses capability intent plus replaceable
  provider choice — never the assumption that a capability exists
  because a vendor does. Provider entries carry `mode` and
  `replaceable`; they never carry `config` or `requires_secrets`
  (`validate_settings_export`).
- **world-export** preserves the user's intentional provider
  selections according to classification rules; no secrets ever.
- **backup** may preserve full provider configuration references
  securely; raw credentials never appear in shareable outputs.

## 8. Compose organization

`compose.yaml` ships exactly one core service. Optional provider
services may be added later through supported mechanisms (profiles,
override files, or separate compose files). The core has no
`depends_on`, `links`, or `network_mode` pointing at any provider
service (`validate_compose_file`). Removing a provider from compose
must never require rebuilding the core architecture.

## 9. Initialization contract

> **Superseded for the front door by [ADR-0008](adr/0008-front-door.md) (2026-10-01):** the front-door rebuild initializes the C1 config files under `$PW_CONFIG_DIR/worlds/…` and `owner.yaml`, with durable state in `$PW_DATA_DIR/worlds.db`. See [`docs/rebuild/CONTRACTS.md`](rebuild/CONTRACTS.md) C1/C7 and [`docs/rebuild/DURABILITY.md`](rebuild/DURABILITY.md). The table below describes the retired app.

`personal-world init` creates, idempotently and secret-free:

| Artifact | Purpose |
|---|---|
| `world.json` | empty world + `schema_version` stamp |
| `journal.ndjson` | append-only journal |
| `connections.json` | empty — a valid zero-provider install |

First boot never depends on a provider marketplace or interview
wizard. `schema_version` mismatches fail explicitly, never silently
reinterpreted.

## 10. UI implications

Worlds navigation and presentation are organized around World
concepts and user tasks (currently Bridge as home, plus Memory, Chat,
Interests, Settings and Crew), never
third-party product names. An Apps/Services view and provider deep
links are secondary navigation. The generic capability contract is
what the dashboard renders; vendor vocabulary lives only in
namespaced provider detail at most.

## 11. Design tool independence

Design semantics are core-owned; design tools are replaceable
machinery. The same principle extends to design tooling:

```text
Worlds design contract
        ↓
portable semantic artifacts (design/tokens.json, docs, tests)
        ↓
design provider / implementation tool
        ├── Figma
        ├── Penpot
        ├── code-first implementation
        └── future tools
```

- Canonical design sources are kept in repo-native, portable formats
  (`design/tokens.json`, dashboard HTML/CSS, accessibility model).
- Never a `.fig`, Figma project ID, Figma API response, or
  Figma-specific component structure as canonical product truth.
- Design tokens are semantic (`surface.canvas`, `text.primary`,
  `status.healthy`, `focus.ring`), not tool-internal. Generated
  Figma variables or CSS custom properties are derived artifacts.
- Accessibility semantics (motion, contrast, text_scale, density,
  targets) live in the core `Accessibility` model. A design tool
  implements them; it does not own them.
- A contributor must be able to clone Worlds, inspect its
  design and accessibility contract, and implement or redesign it
  without any design tool. `DESIGN-HANDOFF.md` is a tool-neutral
  *design implementation handoff*; a Figma-specific section within
  it is allowed, Figma-as-architecture is not.

## 12. Conformance requirements

`tests/test_framework.py` is the conformance suite. It proves:

- **A. Core-only:** boots; every capability explicit `not_configured`;
  API, CLI, dashboard work (`TestCoreOnly`).
- **B. Provider added:** capability richer; canonical concept
  unchanged (`test_provider_added_capability_richer_concept_unchanged`).
- **C. Provider unavailable:** core healthy; degraded reported
  as unavailable; unrelated capabilities unaffected (`test_provider_unavailable_...`).
- **D. Provider removed:** no corruption; baseline remains;
  provider-specific data does not masquerade as current
  (`test_provider_removed_no_corruption`).
- **E. Substitution:** a real forge adapter → fake through one
  contract without changing the user-facing capability model
  (`test_fake_provider_substitution_preserves_capability`).
- **Init:** fresh init succeeds, zero-provider installs boot,
  bootstrap has no secrets, init is idempotent, providers can be
  added later, provider-config removal keeps core state, schema
  mismatch is explicit (`TestInit`).
- **Validator:** each violation class is caught and the repo's own
  config passes its own validator (`TestValidator`).

Run: `uv run pytest tests/test_framework.py` and
`personal-world framework validate`.

## 13. Capability manifest

`personal-world manifest` and `GET /api/manifest` answer, per
capability: what exists, native baseline?, which providers can
enrich, which is active, what happens if that provider disappears.
The manifest is the shared capability-discovery surface for CLI/API clients
and future capability-driven onboarding; do not assume every current UI
consumes it.

## 14. Current setup and future capability interview

`/setup` is the live first-run "First Light" wizard (auth choice,
comfort, crew on/off, companion choice); the older `/setup-wizard` page
alias is gone — only its `/api/setup-wizard/*` API routes remain.
`/api/setup` initializes
the instance token and can initialize the native vault. These are not
the complete capability/accessibility interview below. Zero-provider
CLI initialization remains supported without completing a wizard.

The framework supports this richer target flow:

```text
What would you like Worlds to help with?
        ↓
enable capability → native baseline available immediately
        ↓
connect an existing provider for richer functionality? (optional)
```

Never: "choose between 37 vendor integrations before you can begin."

## 15. Anti-patterns (rejected)

| Anti-pattern | Example |
|---|---|
| Provider-shaped core | `source_control == Gitea` |
| Required optional services | core cannot boot without Traefik |
| Vendor-specific canonical schemas | canonical ingress object == raw Traefik router JSON |
| UI duplication | Worlds implements an entire Git client |
| Capability disappearance | Gitea removed → source control concept vanishes |
| Silent degradation | provider offline → old observation shown as healthy |
| Secret-bearing manifests | providers.yaml contains API tokens |
| Compose lock-in | using provider X requires rewriting the whole stack |
| Design-tool lock-in | dashboard cannot be modified without a Figma workspace |
| Figma tokens canonical | code tokens generated from Figma instead of repo tokens |

## 16. Keep the framework small

V0 needs strong contracts, not machinery. No operator framework, no
plugin marketplace, no dynamic plugin execution, no event bus, no
giant SDK. Prefer: typed schemas, registry metadata, explicit adapter
interfaces, tests, docs, small validators.
