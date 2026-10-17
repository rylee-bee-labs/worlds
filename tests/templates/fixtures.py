"""Golden fixtures for test templates.

Each function returns a ready-to-use dict or World instance.
Copy this file alongside your test, import what you need, replace values.

Usage:
    from tests.templates.fixtures import healthy_service, stale_service
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from personal_world.envelope import Result  # noqa: E402
from personal_world.model import (  # noqa: E402
    Capability,
    Fact,
    Policy,
    PolicyEffect,
    Provenance,
)
from personal_world.providers.registry import (  # noqa: E402
    Registry,
    StatusContract,
)
from personal_world.status import Status  # noqa: E402
from personal_world.world import World  # noqa: E402

# ---------------------------------------------------------------------------
# Capability fixtures
# ---------------------------------------------------------------------------

def healthy_service() -> World:
    """A world with one capability reporting healthy."""
    w = World()
    prov = Provenance(source="test:fixtures")
    w.register_capability(Capability(key="source_control"))
    w.record_fact(Fact(
        key="capability.source_control.status",
        value=Status.HEALTHY.value,
        provenance=prov,
    ))
    return w


def unknown_service() -> World:
    """A world with one capability in UNKNOWN state (no check has run)."""
    w = World()
    prov = Provenance(source="test:fixtures")
    w.register_capability(Capability(key="memory"))
    w.record_fact(Fact(
        key="capability.memory.status",
        value=Status.UNKNOWN.value,
        provenance=prov,
    ))
    return w


def stale_service() -> World:
    """A world with one capability whose observation is very old."""
    w = World()
    old_prov = Provenance(
        source="test:fixtures",
        observed_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    w.register_capability(Capability(key="discovery"))
    w.record_fact(Fact(
        key="capability.discovery.status",
        value=Status.HEALTHY.value,
        provenance=old_prov,
    ))
    return w


# ---------------------------------------------------------------------------
# Conflict fixtures
# ---------------------------------------------------------------------------

def conflicting_sources() -> dict:
    """Two providers disagreeing on the same capability.

    Returns a dict with 'world', 'registry', and the two provider names so
    tests can assert that the conflict is surfaced.
    """
    w = World()
    w.register_capability(Capability(key="source_control"))

    class HealthyProvider(StatusContract):
        def observe(self):
            return Result(ok=True, status="healthy",
                          data={"provider": "primary"})

    class UnhealthyProvider(StatusContract):
        def observe(self):
            return Result(ok=False, status="unavailable",
                          warnings=["connection refused"])

    reg = Registry()
    reg.define_capability("source_control", StatusContract)
    reg.register("source_control", "primary", HealthyProvider(),
                 health_check=lambda: True)
    reg.register("source_control", "secondary", UnhealthyProvider(),
                 health_check=lambda: False)

    return {
        "world": w,
        "registry": reg,
        "primary": "primary",
        "secondary": "secondary",
    }


# ---------------------------------------------------------------------------
# Authorization fixtures
# ---------------------------------------------------------------------------

def unauthorized_action() -> World:
    """A world with a cemented deny policy that blocks non-user mutation."""
    w = World()
    prov = Provenance(source="user:explicit")
    w.set_policy(Policy(
        key="content.animal_cruelty",
        effect=PolicyEffect.DENY,
        provenance=prov,
    ))
    w.cement("content.animal_cruelty")
    return w
