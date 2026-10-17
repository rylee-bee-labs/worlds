# CI Environment Notes — the traps we already ate

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the CI environment traps a local run must match · **Read this if:** your local suite passes but CI fails (or the reverse), or you are setting up a new machine.

**In short:** the handful of environment mismatches that have silently flipped a suite green locally and red in CI. Most of it is one idea: sync the same extras CI does (`--extra test --extra crypto`) and always read a checker's real exit code, not its piped output.

A new contributor's environment must match CI's, or a green suite locally
turns red in CI (and the reverse). The traps below were first verified
2026-09-20. Since then the workflow's *mechanics* moved to
`Rylee-Bee/ci-harness` (reusable workflows); this repo's
`.github/workflows/validate.yml` now passes only the arguments, so the
Python and `uv` versions are no longer in this repo — see that harness.
As of 2026-09-26 its `reusable-python.yml` defaults are Python `3.12` and
`uv` `0.11.28`, and this repo passes neither, so it uses those defaults.

## 1. The sync line is `uv sync --frozen --extra test --extra crypto`

The CI `test` job syncs `sync-args: "--extra test --extra crypto"` and runs
pytest with `--timeout=30` (both set in `.github/workflows/validate.yml`):

```bash
uv sync --frozen --extra test --extra crypto
uv run pytest --timeout=30
```

`--frozen` means the lockfile decides versions; do not "helpfully" re-resolve
it in a CI path. Other jobs sync a subset (`--extra test` alone for browser
and framework gates) — see the workflow file for which extra belongs to which
job. Locally, run the full line above unless you know why you would not.

## 2. `pytest` needs httpx because starlette's TestClient demands it

Most API tests (`tests/test_api_*.py` and friends) build a
`starlette.testclient.TestClient`. That module imports an HTTP client at
import time; with none installed, collection dies before the first test:

```text
RuntimeError: The starlette.testclient module requires the httpx2 package
to be installed.
```

(the exact package named in that message depends on the starlette version in
the lock: 1.6.0 prefers `httpx2` and warns that plain `httpx` is deprecated;
older builds said "the httpx package" — same trap, one rename). The fix is
never to install anything ad-hoc: `httpx` is in the `test` extra in
`pyproject.toml`, so line 1 above already carries it. Symptom check:

```bash
uv run --frozen python -c "from starlette.testclient import TestClient"
```

## 3. Drop `--extra crypto` and the backup suite fails closed with 503s

`personal_world.worlds_backup` (the encrypted SOS escape hatch) imports
`cryptography` optionally and **fails closed** without it: `backup()` and
`restore()` return `status: "unavailable"` and write nothing, and the wired
routes map `unavailable → HTTP 503` (`worlds_backup.py`, the
`register_worlds_backup` routes). A suite run without `--extra crypto`
therefore turns every backup/restore round-trip test red or 503 — not because
the code is broken, but because the product refuses to make an unencrypted
"backup". No plaintext fallback exists by design (`tests/test_worlds_backup.py::
`test_missing_crypto_extra_fails_closed` pins that behaviour). The same story
holds for the native vault; see `docs/OPERATIONS.md`.

## 4. Capture `$?` before piping command output

`bash` returns the exit code of the LAST pipeline stage, so a checker that
reports through a pipe looks green while it screams:

```bash
lab share check file.md | jq -r '.hits'   # $? here is jq's, not the canary's
```

Capture the real code at the source, before any pipe consumes the status:

```bash
lab share check file.md >/tmp/out.json 2>&1; rc=$?
```

or with a pipeline in play, read the array element: `rc=${PIPESTATUS[0]}`,
or set `set -o pipefail` for the block. This bit us with the share canary in
a nightly wrapper; the same rule governs pytest summary greps, `vale` JSON
piping, and every "pass if the pipe printed something" idea. A gate that
cannot see its tool's exit code is decoration.

## Quick parity checklist for a new box

```bash
uv sync --frozen --extra test --extra crypto   # 1
uv run python -c "import httpx, cryptography; from starlette.testclient import TestClient"  # 2+3
# 4: any wrapper script that gates on output, not on rc, is wrong
```
