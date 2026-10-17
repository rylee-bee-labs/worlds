# Worlds — Degraded Modes Matrix (G-degrade)

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** what the product says and does when a part of it is missing, unreachable, refused, or unauthenticated · **Read this if:** you are changing a fail-closed path or a degraded label.

**In short:** when something is missing or broken, Worlds keeps the rest working and
says exactly what is wrong. This page lists each case, what still works, the label
it shows, and the test that checks it. In every tested case the product reports
`unavailable`, `stale` or `not_configured` instead of pretending to succeed, and it
never shows a button that looks usable but does nothing.

**Rule this page checks:** principle 3 of `docs/PRODUCT-LANGUAGE.md` (owner-approved
2026-09-21): *warm in tone, exact in facts.* A degraded state must be reported as
degraded, without blaming the person.
**Tests:** [`../tests/test_degraded_modes.py`](../tests/test_degraded_modes.py)
(32 tests, ids `a1`–`h4` below, as of 2026-09-26). Where an older test already
covers the same case, it is listed too.
**Last full run:** branch `lane/degraded-matrix` @ `58f3b5e` (2026-09-21), no
defects. Re-run `uv run --extra test pytest -q tests/test_degraded_modes.py` for
today's result. Three label observations are at the bottom; none is a defect.

Most rows rely on the provider registry
([`../src/personal_world/providers/registry.py`](../src/personal_world/providers/registry.py)):
a missing or unhealthy provider returns a labelled `Result` instead of raising an
exception or returning a made-up value.

## How to read a row

| Column | Meaning |
| --- | --- |
| Still works | What keeps working |
| Says | What is degraded, the exact label shown, and the HTTP response |
| Tested by | Test ids. `DM:` = `test_degraded_modes.py`; ids are `Class::method` abbreviations |

---

## (a) No model configured (the default)

Worlds ships with **no model configured**. That is an empty slot, not an error, so
the daily digest does not raise an alert for it.

| | |
| --- | --- |
| **Still works** | Everything that doesn't need a model: `/api/status`, `/api/daily`, journal, sections, settings, vault, backup |
| **Says** | `/api/chat` → HTTP 200 `{ok:false, status:"not_configured"}` with the warning "no chat provider configured" · `/api/chat/test` → same · `/api/chat/providers` → `active: null` · capability grid: `reasoning: not_configured` · the Bridge's attention line does **not** list empty slots (only real problems) |
| **Tested by** | `DM:TestBrainAbsent::a1–a5`; also `test_chat.py::TestChatEndpoint::test_no_provider_is_not_configured` |

## (b) Model configured, but its server is down

A connection is configured (for example Ollama) but nothing answers. The test uses a
real closed local port, so the error is a real `ConnectionRefusedError`.

| | |
| --- | --- |
| **Still works** | The core starts and answers 200: `/healthz`, `/api/status`, `/api/daily` (the digest itself is `ok:true`) |
| **Says** | Capability grid: `reasoning: unavailable` · the Bridge's attention line shows `reasoning: unavailable` (the Bridge's internal area id is `overview`) · `/api/chat` → 200 `{ok:false, status:"unavailable"}` with **no reply text** · `/api/chat/providers` lists the provider with `ok:false` and its real status |
| **Tested by** | `DM:TestBrainUnreachable::b1–b4` |
| **Not tested** | A server that hangs instead of refusing. It goes through the same code path after `CHAT_TIMEOUT_SECONDS`, but a test would need a long timeout and would be flaky, so it isn't included |

## (c) Provider answers with an error

The provider is reachable but refuses (bad or expired key, quota, a 4xx from the
provider).

| | |
| --- | --- |
| **Still works** | The request completes with HTTP 200 and the provider's own label |
| **Says** | `/api/chat` passes the provider's status through unchanged (for example `unauthorized`, warning `api key not valid`). It is not replaced with a generic "something went wrong", not reported as healthy, and no reply is invented. A control test shows a working provider's reply does come through, so a missing reply here means the provider refused |
| **Tested by** | `DM:TestProviderErrorEnvelope::c1–c2` |

## (d) Setup not finished (no `data/setup-complete` marker)

| | |
| --- | --- |
| **Still works** | `/healthz` (`setup_needed: true`), `/api/setup/status` (`complete: false`), `GET /` → 303 → `/setup`, and the setup wizard at `/setup` (200 HTML) |
| **Says** | Setup and sign-in are **separate**: unfinished setup never opens the API (protected routes still answer 503 without a token), and writing the marker only changes `setup_needed` |
| **Tested by** | `DM:TestSetupIncomplete::d1–d4`; also `test_setup_wizard.py`, `test_api_hardening.py::COR-12` (`FORCE_SETUP=1` reopens setup), `test_boot_token.py`, `test_critical_batch.py` (init writes the marker) |

## (e) No sign-in configured (no token anywhere)

No `PW_API_TOKEN` in the environment and no `data/.env` store.

| | |
| --- | --- |
| **Still works** | `/healthz` (200 with `auth_configured: false`, so the state is visible), the `/setup` wizard, `/api/setup/status`, the login page |
| **Says** | Every protected route → **503 `auth not configured`**. A token sent to an instance with no stored credentials also gets 503; it never falls through to success. 503 means "this instance has no sign-in set up yet"; 401 means "that key didn't work" |
| **Tested by** | `DM:TestAuthUnconfigured::e1–e4`; also `test_dev_auth_bypass.py::TestBypassBehavior::test_off_no_token_fails_closed` |

## (f) `PW_DEV_AUTH_BYPASS` set, request from another machine

The bypass is a development shortcut that only applies to requests from the same
machine (loopback). From anywhere else it has no effect. The test sets the request's
peer address (the value `_is_true_loopback` reads) to a documentation-range address,
so the real check runs.

| | |
| --- | --- |
| **Still works** | Normal sign-in from the other machine: the right token → 200; `/healthz` **still shows `dev_bypass: true`** to everyone, so the risky setting is visible |
| **Says** | Other machine + no credentials → 503 (bypass not applied) · wrong or missing token → 401 · right token + a write → 403 `write requires step-up auth` (the bypass never grants step-up) · `POST /api/setup`, which creates credentials, → 403 from another machine **even with the bypass on**, so no one on the network can take over a fresh instance |
| **Tested by** | `DM:TestBypassNonLoopback::f1–f5`; also `test_dev_auth_bypass.py::TestLoopbackDetection`, `test_step_up_authority.py::TestStepUpSeam` |

## (g) Journal and Memory with no extra provider

Memory is **not** an AI feature. The core always registers a built-in search over the
journal (`native-memory`, SQLite FTS5; see `build_registry` in
`../src/personal_world/app.py`). So "no provider" for memory means no *extra* provider,
and nothing degrades. The one thing that is missing, `reasoning: not_configured`, is
labelled next to it. Chat is always optional: everything here works without it.

| | |
| --- | --- |
| **Still works** | Journal: write a note, read it back, see it in the audit log, with zero providers · Memory search finds that note with no external connection · the capability grid shows `memory: healthy` (built-in) next to `reasoning: not_configured` |
| **Says** | Nothing claims AI features that aren't there; semantic search (for example a `langgraph` memory provider) is simply off until configured |
| **Tested by** | `DM:TestJournalMemoryWithoutProvider::g1–g3`; also `test_journal_supersede.py`, `test_framework.py` (built-in baseline) |

## (h) Storage and backup

| Case | State | What happens | Tested by |
| --- | --- | --- | --- |
| h-1 | Vault without the `cryptography` extra | Unlock **refuses**: `{ok:false, status:"unavailable"}`; `/api/vault/status` reports `locked:true, encrypted:false`. It never claims to be encrypted | `DM:h1`; also `test_vault_fail_closed.py` (both flip the same module flag a crypto-less install really has) |
| h-2 | Worlds backup without crypto | `POST /api/worlds/backup` → **503** with "unavailable without real encryption"; no archive and no partial file | `DM:h2`; also `test_worlds_backup.py::test_missing_crypto_extra_fails_closed`, `::test_real_app_refuses_and_serves_backup` |
| h-3 | Chat transcript can't be written (a real `OSError`: a directory sits where the file should be) | The chat **reply still arrives** (200, `ok:true`) and the write failure is **logged** | `DM:h3, h3b` (the rule is stated in `api.py`: a transcript write failure must never hide the reply) |
| h-4 | Search index corrupted (garbage bytes in `data/memory.fts5.db`) | Memory search → 200 `{ok:false, status:"unavailable"}`; the capability grid says `unavailable`; **the journal itself is untouched** and still reads back. The index can always be rebuilt from the journal files | `DM:h4` |
| h-5 | Disk full (ENOSPC) during a write | **Not tested:** it needs a real full filesystem, and mounting one needs privileges the test run doesn't have. Faking it would test the fake, not the product. The nearby cases (unwritable path, corrupt file) are h-3 and h-4 | — |
| h-6 | Writing to read-only storage (`chmod 0555` data dir; checked by hand 2026-09-21: `POST /api/daily` and `POST /api/journal` raise `PermissionError`, which a running server returns as 500) | **No labelled state is promised yet.** The write fails visibly (never a fake `ok:true`), and reads keep working: `GET /api/daily` returns 200 with the warning `memory: unavailable` because the index can't be built | manual check; no test pins it, because a test would lock in the 500 as expected behaviour (see observation 3) |

---

## Observations (not defects)

1. **`/api/chat/providers` `active` names a provider that is down.** In case (b),
   `active` is the configured provider's name while its own entry says
   `ok:false, status:"unavailable"`. `active` means "which provider is configured",
   not "which one is answering", and the real status is in the same response. Clearer
   names (`wired` and `ready`) would help; noted here for a later wording pass.
2. **`NativeMemoryProvider.health()` always returns `True`**
   (`../src/personal_world/providers/native_memory.py`). So the built-in memory is
   always selected, but every status shown to people comes from `observe()` and
   `search()`, so a broken index still shows `unavailable` (checked by `DM:h4`). A
   real health check would be an improvement, not a fix.
3. **A failed write to storage returns 500 (h-6).** Checked against a read-only data
   directory: `POST /api/daily` and `POST /api/journal` raise `PermissionError` (500
   on a running server). Nothing pretends to succeed and reads still work, but a
   plain "storage unavailable" response would match the product language better.
   Flagged for a later decision.

## Test helpers reused (nothing new added)

- `create_app(tmp_path, tmp_path)` + `TestClient` + strict env `monkeypatch`:
  `test_dev_auth_bypass.py::_client`
- Module-flag patching to simulate real install variants (no crypto):
  `test_vault_fail_closed.py`
- Registering providers through the app's own registry (`build_registry` patch):
  `test_chat.py::TestChatEndpoint`
- Documentation-range peer addresses marked `pw-safety: synthetic`:
  `test_step_up_authority.py`
- Loopback step-up and bypass precedence: `test_dev_auth_bypass.py::TestBypassBehavior`

**Related docs:** `ARCHITECTURE.md` (registry and fail-closed core) · `OPERATIONS.md`
(token and store recovery) · `WORLDS-BACKUP.md` (h-2) · `IDENTITY-BOUNDARY.md`
(sign-in and step-up, row f) · `PROVIDERS.md` (built-in vs extra providers, row g).
