# Framework gate: old rules → new rules (ADR-0008)

> **Status:** Accepted 2026-10-01 · **Canonical for:** the mapping from the retired ADR-0001 framework rules to the front-door `personal-world framework validate` gate · **Read this if:** you are changing `src/personal_world/framework.py`, `tests/test_framework.py`, the `framework-gates` CI job, or wondering why an old rule is gone.
> **Authority:** [ADR-0008](../adr/0008-front-door.md) (decision 3 retires the capability registry for front-door providers) · **Baseline:** `.project/PROPOSAL-FRONT-DOOR-2026-10-01.md` (S6).

**In short:** after ADR-0008 the gate validates the *new* product (C1 config, recipes, the zero-provider baseline, compose additivity, Memory exports) instead of the ADR-0001 capability registry. The CLI verb, the JSON envelope and the exit-code semantics are unchanged; only the rule names and the objects they inspect change.

## The gate today

`personal-world framework validate --json` runs five retained rules plus the untouched Play-Nice participant-pack gate. Every rule reads only `personal_world.worlds.*`; the retired ADR-0001 modules (`app`, `model`, `world`, `init`, `providers`, `api`, …) are never imported, so the gate survives their deletion.

| Rule | What it checks | Source |
| --- | --- | --- |
| `config-invalid`, `config-reference` | every C1 object loads through the real `ConfigStore` (schema, ids, `extra=forbid`, dangling references); last-valid semantics untouched; never writes | ADR-0008 decision 3, decision 5; C1 |
| `secret-rule` | no inline secret material anywhere in config; only `secret_ref: env:/vault:/file:` (defence in depth over the C1 models) | ADR-0008 decision 3; ADR-0007; C1 |
| `recipe-*` | every `config/recipes/` recipe loads, declares `verified` + `status`, uses only synthetic hosts, carries no secret value | recipes contract; C1 |
| `boot-baseline` | the app boots with an EMPTY config dir and answers `/healthz` (200 ok) and `GET /api/boards/home` (200, `first_run` true) | ADR-0008 decision 2 |
| `compose-additive` | no core compose service depends on an optional provider service | ADR-0008 decision 2; native baseline |
| `pack-*` | every participant pack parses, has `schema`/`id`, a `play-nice/` namespace and unique ids | Play-Nice participant-pack gate (unchanged) |

The shareable Memory export path (`/api/memory/export/{table}`) is scanned with the same `secret-rule` by running the real `MemoryStore.export_ndjson` over a throwaway store (ADR-0008 decision 8).

## Mapping

| Old rule (old enforcement) | New rule / retired | Why (ADR-0008 line) |
| --- | --- | --- |
| `provider-registry` — connections must be a list; each entry needs type/name/capability | **retired** | The connection registry is replaced by C1 provider files (`worlds/providers/<id>.yaml`); schema and ids are enforced by `config-invalid`. Decision 3 (line 11). |
| `capability-ownership` — a provider may only claim a core-registered capability | **retired** | "ADR-0001's capability registry is retired for front-door providers." Meaning moves into Mapping `concept` metadata. Decision 3 (line 11); proposal S6 (line 360). |
| `provider-mode` — mode must be in the closed enrichment/authority vocabulary | **retired** | Provider modes were part of the ADR-0001 capability model; a C1 provider declares `kind`, not a capability mode. Decision 3 (line 11). |
| `optional-default` — `required: true` needs a `required_reason` | **retired / replaced** | There is no `required` flag to gate in C1; a provider cannot become a boot dependency because of `compose-additive` plus the zero-provider baseline. Decisions 2–3 (lines 10–11). |
| `provider-registry` — duplicate provider id | **retired** | Provider paths are keyed by id; a duplicate filename is the same object, and an id/path mismatch is `config-invalid`. C1; decision 5 (line 17). |
| `secret-rule` — inline secret keys in a connection | **retained, re-pointed** | Same shape scan, now over every C1 config object, every recipe, and every Memory export row. Decision 3 (line 11). |
| `compose-additive` — core cannot depend on a provider | **retained (unchanged meaning)** | Providers stay additive; the provider names now come from the loaded C1 config, not `connections.json`. Decision 2 (line 10). |
| `export-portability` — settings-export must not carry `config`/`requires_secrets` | **retired** | The settings-export blueprint expressed the capability/provider split; the export path that matters now is Memory (`/api/memory/export/{table}`), scanned by `secret-rule`. Decision 3 (line 11); decision 8 (line 20). |
| — (not a framework.py rule) `TestCoreOnly`, `TestProviderLifecycle`, `TestInit`, `TestManifest`, `TestProviderClassificationGuard`, `TestProviderHealthCheckBinding` | **retired** | They exercised the ADR-0001 world model and imported retired modules; the zero-provider baseline test replaces the boot half of `TestCoreOnly`. Decision 3 (line 11); decision 7 (line 19). |
| participant-pack gate (`pack-*`) | **retained** | Play-Nice participant packs are orthogonal to the front-door provider model. ADR-0008 does not touch them. |

## CLI contract (unchanged)

- Verb: `personal-world framework validate [--json]` (and `framework validate-packs`).
- JSON envelope keeps `ok` / `status` at the top level and `data.violations` (now a list of `{"rule", "detail"}` objects) plus `data.count`.
- Exit codes: `0` clean, `EXIT_ERROR` (nonzero) with `status: "unhealthy"` and one warning per violation otherwise.
- CI (`framework-gates`) runs `pytest tests/test_framework.py` then `uv run personal-world framework validate --json`; neither command changed.

## Tests

`tests/test_framework.py` gives every retained rule a passing case and a failing fixture, boots the zero-provider baseline directly, and drives the CLI end-to-end (`clean → exit 0`, violation → nonzero). The deleted classes are listed in the mapping table above. No test imports a retired module.
