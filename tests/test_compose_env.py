"""Production compose passes through every variable the production app reads.

The recurring trap (Rylee, 2026-10-08: "this block has caused lots of errors I've seen before"): compose hands the
container ONLY the names listed under `environment:`. A variable set in `/opt/personal-world/.env` that is not listed
there never reaches the app, and nothing complains; the feature just reads "not configured". Web Push shipped that
way: `PW_VAPID_*` were documented but never forwarded.

This test collects every `PW_*` name the front-door production app's code mentions and fails when one is neither
forwarded by `compose.yaml` (service `core`), nor set by the image (`ENV` in the Dockerfile), nor listed below with
the reason production does not need it.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
# The production app (Dockerfile CMD: personal_world.worlds.production:app_from_env) and the modules it mounts.
PRODUCTION_CODE = [*sorted((ROOT / "src/personal_world/worlds").rglob("*.py")),
                   ROOT / "src/personal_world/push.py", ROOT / "src/personal_world/oidc.py"]
NAME = re.compile(r"\bPW_[A-Z0-9_]+\b")

# Mentioned by the production code, deliberately NOT forwarded. Each needs a reason a reviewer can check.
NOT_FORWARDED = {
    "PW_DEV_DIR": "worlds/dev.py only: the local dev server, never the image",
    "PW_RECIPES_DIR": "defaults to the recipes shipped in the image",
    "PW_ROLE_GROUPS": "optional OIDC group-to-role mapping; unset means no role mapping",
    "PW_COMPANION_TOKEN_FILE": "named by config (`secret_ref: file:...`) and mounted as a file, not an env value",
    "PW_STATIC_DIR": "defaults to the UI the image builds into personal_world/static/app; only tests and local runs point it elsewhere",
}


def _code_names() -> set[str]:
    return {m for path in PRODUCTION_CODE for m in NAME.findall(path.read_text())}


def _forwarded() -> set[str]:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    env = compose["services"]["core"].get("environment") or {}
    names = set(env if isinstance(env, dict) else (e.split("=", 1)[0] for e in env))
    for line in (ROOT / "Dockerfile").read_text().splitlines():
        if line.startswith("ENV "):
            names.update(re.findall(r"\b(PW_[A-Z0-9_]+)=", line))
    # An ENV instruction can continue over several lines (`ENV A=1 \` / `    B=2`).
    names.update(re.findall(r"^\s+(PW_[A-Z0-9_]+)=", (ROOT / "Dockerfile").read_text(), re.M))
    return names


def test_every_variable_the_production_app_reads_reaches_it():
    missing = _code_names() - _forwarded() - set(NOT_FORWARDED)
    assert not missing, (
        f"the production app reads {sorted(missing)} but compose.yaml (service core) does not pass them through, so "
        "setting them in .env does nothing. Add `NAME: ${NAME:-}` under core.environment, or list the name in "
        "NOT_FORWARDED with the reason production does not need it.")


def test_the_push_and_sign_in_variables_are_forwarded():
    # The ones that already went missing once, named so a refactor of the scan cannot quietly drop them.
    assert {"PW_VAPID_PRIVATE_KEY", "PW_VAPID_SUBJECT", "PW_BOOTSTRAP_TOKEN", "PW_TRUSTED_PROXIES"} <= _forwarded()


def test_the_exceptions_are_still_real():
    stale = set(NOT_FORWARDED) - _code_names()
    assert not stale, f"NOT_FORWARDED lists {sorted(stale)}, which the production code no longer mentions; remove them"
