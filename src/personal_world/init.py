"""Initialization contract (framework Rule 12).

`personal-world init` creates everything a fresh standalone install
needs BEFORE first boot, with zero optional providers configured:

- local World state (empty facts/intents/policies/lore, default packs)
- native baseline config (empty connections: {} — valid, not broken)
- journal file
- provider registry seed (capabilities from the core, no providers)
- presentation defaults (accessibility profile)
- schema_version stamp for future migrations

It is idempotent: re-running on an initialized world detects existing
state and changes nothing. It writes no secrets. First boot never
depends on a provider marketplace or interview wizard.
"""

import json
from pathlib import Path

from .envelope import Result, ok
from .journal import Journal
from .model import SCHEMA_VERSION


def init_stores(data_dir: Path, config_dir: Path) -> tuple[list[str], list[str]]:
    """Create-if-absent world/journal/connections stores. NO marker.

    Extracted from ``init_world`` so the first-run setup wizard can
    provision the exact same stores without completing setup: only
    ``init_world`` (the CLI contract) writes the setup-complete marker.
    Never overwrites anything; returns ``(changed, skipped)``.
    """
    data_dir = Path(data_dir)
    config_dir = Path(config_dir)
    world_path = data_dir / "world.json"
    conn_path = config_dir / "connections.json"

    changed: list[str] = []
    skipped: list[str] = []

    # 1. World state: create only if absent; never clobber user state.
    if world_path.exists():
        skipped.append("world.json exists")
    else:
        world_path.parent.mkdir(parents=True, exist_ok=True)
        world_path.write_text(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "facts": {},
                    "intents": {},
                    "policies": {},
                    "lore": {},
                    "capabilities": {},
                    "providers": {},
                    "packs": {},
                    "accessibility": {
                        "motion": "reduced",
                        "contrast": "normal",
                        "text_scale": 1.0,
                        "density": "normal",
                        "targets": "normal",
                    },
                },
                indent=2,
            )
        )
        changed.append("created world.json")

    # 2. Journal: touching the file is enough; Journal appends lazily.
    journal = Journal(data_dir / "journal.ndjson")
    if journal.path.exists():
        skipped.append("journal.ndjson exists")
    else:
        journal.path.touch()
        changed.append("created journal.ndjson")

    # 3. Native baseline config: an EMPTY connections file is a valid
    # zero-provider install. Providers are added later, additively.
    if conn_path.exists():
        skipped.append("connections.json exists")
    else:
        conn_path.parent.mkdir(parents=True, exist_ok=True)
        conn_path.write_text(
            json.dumps(
                {
                    "$schema": "personal-world/connections/1",
                    "connections": [],
                },
                indent=2,
            )
        )
        changed.append("created connections.json (zero providers: valid)")

    return changed, skipped


def init_world(data_dir: Path, config_dir: Path) -> Result:
    """Initialize a fresh Personal World. Idempotent, secret-free."""
    data_dir = Path(data_dir)
    config_dir = Path(config_dir)

    changed, skipped = init_stores(data_dir, config_dir)

    # 4. First-run contract: the SPA's setup gate reads the
    # setup-complete marker (api.py healthz/setup-status). A CLI
    # initialization IS first-run setup for the zero-provider world,
    # so satisfying the marker here means `personal-world init` +
    # launch opens the app without manual sentinel surgery. The
    # wizard's richer bootstrap (token + stores + search index — no
    # vault step, by owner decision 2026-09-22) stays available at
    # /setup; init only fulfills the marker contract and never
    # overwrites an existing world.
    marker_path = data_dir / "setup-complete"
    if marker_path.exists():
        skipped.append("setup-complete marker exists")
    else:
        marker_path.write_text("ok")
        changed.append("created setup-complete marker (first-run satisfied)")

    return ok(
        "initialized" if changed else "already-initialized",
        changed=bool(changed),
        actions=changed,
        warnings=skipped,
        data={
            "data_dir": str(data_dir),
            "config_dir": str(config_dir),
            "schema_version": SCHEMA_VERSION,
            "providers_configured": 0,
        },
    )
