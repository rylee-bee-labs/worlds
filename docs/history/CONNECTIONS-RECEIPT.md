# CONNECTIONS & PROVIDERS — RECEIPT (audited)

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

# implementation commit: ee488b1
# receipt commit: 353e04c
# audit fix commit: 0e3d940
# audited receipt commit: f73df40

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/CURRENT.md`) · **Read this if:** you need the 2026-09-13 Connections/Providers audit's own counts and test-behavior table. · **Superseded by:** `.project/CURRENT.md`.

**In short:** a 2026-09-13 audit receipt claiming 725 tests, 7 capabilities and 18 providers. Kept for provenance; treat no count as current. Since this record: the product is called Worlds and providers are registered against the current capability set, not this snapshot.

---

## TESTS

**725 passed, 0 failed, 0 warnings**

---

## PROVIDER COUNTS (derived from code)

| Capability | Providers | Count |
|------------|-----------|-------|
| media | plex, sonarr, radarr, lidarr | 4 |
| calendar | ics, caldav | 2 |
| notifications | webhook, ntfy | 2 |
| deployment | compose, systemd, lab_cli | 3 |
| update_discovery | github_release, version_url | 2 |
| auth | oidc | 1 |
| reasoning | ollama, openai_compat, openai, anthropic | 4 |
| **Total** | | **18** |

7 capabilities, 18 providers.

---

## TEST/VALIDATION BEHAVIOR (per provider)

| Provider | can_test | Test type | Detail |
|----------|----------|-----------|--------|
| plex | True | live | HTTP GET to server |
| sonarr | True | live | HTTP GET to /api/v3/system/status |
| radarr | True | live | HTTP GET to /api/v3/system/status |
| lidarr | True | live | HTTP GET to /api/v3/system/status |
| ics | True | live | HTTP HEAD to feed URL |
| caldav | **False** | — | No live CalDAV probe implemented |
| webhook | True | **local** | URL accepted, not fired |
| ntfy | True | live | HTTP GET to /v1/health |
| compose | True | **local** | File existence check |
| systemd | True | **local** | Service name accepted, no live check |
| lab_cli | False | — | No test implemented |
| github_release | True | live | GitHub API /releases/latest |
| version_url | **False** | — | No live URL probe implemented |
| oidc | True | live | HTTP GET to .well-known/openid-configuration |
| ollama | True | live | HTTP GET to /api/tags |
| openai_compat | **False** | — | No live test (varies by provider) |
| openai | **False** | — | No live API key validation |
| anthropic | **False** | — | No live API key validation |

**Live testable**: 9 (network call to external service)
**Local validation only**: 3 (compose, systemd, webhook — not a connection test)
**No test**: 6 (can_test=False, UI shows no test button)

---

## UI MESSAGING

| Backend status | UI label | When |
|----------------|----------|------|
| `healthy` | Connected | Live network test succeeded |
| `validated` | Configuration validated | Local check passed (compose file found, systemd name accepted, webhook URL accepted) |
| `unavailable` | Unavailable | Network test failed |
| `invalid_configuration` | Invalid configuration | Missing required field |
| `unknown` | Unknown | Catch-all (should not occur — all can_test=True providers have handlers) |

Non-testable providers (can_test=False): UI shows no test button.

---

## CALDAV, VERSION URL, LAB CLI

| Provider | Schema can_test | Backend handler | UI behavior |
|----------|----------------|-----------------|-------------|
| caldav | False | None | No test button shown |
| version_url | False | None | No test button shown |
| lab_cli | False | None (falls through to "unknown") | No test button shown |

---

## REASONING PROVIDERS

| Provider | can_test | Handler | Notes |
|----------|----------|---------|-------|
| ollama | True | Yes (/api/tags) | Live test: lists models |
| openai_compat | False | None | Varies by provider — cannot test generically |
| openai | False | None | Would need live API key validation |
| anthropic | False | None | Would need live API key validation |

Only Ollama has a live test. The other three have can_test=False so the UI does not show a test button.

---

## API ENDPOINTS

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/connections/overview` | Capability overview with status |
| GET | `/api/connections/schemas` | All provider schemas |
| GET | `/api/connections/schema/{cap}` | Single capability schema |
| GET | `/api/connections/config` | Full merged config |
| POST | `/api/connections/config/{key}` | Save native config |
| GET | `/api/connections` | List connections |
| PUT | `/api/connections` | Save connection |
| DELETE | `/api/connections/{name}` | Delete connection |
| POST | `/api/connections/test` | Test connection |
| POST | `/api/connections/validate` | Validate (alias for test) |

---

## PRIVATE CONFIG

- Writes to `connections.local.json` (never tracked `connections.json`)
- Merges with tracked config (local appended, local overrides)
- Hot reload: no restart for routine setup

---

## GIT COMMITS

| SHA | Description |
|-----|-------------|
| 0e3d940 | audit: fix can_test flags and test-result messaging |
| 353e04c | Connections & Providers receipt |
| ee488b1 | Connections & Providers control panel |

---

## FILE LOCATIONS

| File | Path |
|------|------|
| This receipt | docs/CONNECTIONS-RECEIPT.md |
| Provider schemas | src/personal_world/provider_schemas.py |
| Connection manager | src/personal_world/connection_manager.py |
| API endpoints | src/personal_world/api.py |
| Connections panel | frontend/src/screens/ConnectionsPanel.tsx |
| Tests | tests/test_connections.py |
