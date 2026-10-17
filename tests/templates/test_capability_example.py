"""Template: testing a world capability.

Each test protects a specific invariant. Copy this file, replace the
fixture values, and you have a deterministic capability test suite.

Invariants protected:
    - HEALTHY state:  capability returns healthy with evidence in data.
    - UNKNOWN state:  capability returns unknown when no check has run.
    - Unavailable:    provider fails, reports unavailable (never raises).
    - Stale evidence: old observation flagged as stale.
    - Conflicting:    two sources disagree, worst status wins.
    - Boring healthy: nothing interesting to report, world says so.
    - Malformed:      garbage data fails safely, no crash.
    - Provenance:     every status fact carries source and observed_at.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from personal_world.envelope import Result  # noqa: E402
from personal_world.model import (  # noqa: E402
    Capability,
    Fact,
    Provenance,
)
from personal_world.providers.registry import (  # noqa: E402
    Registry,
    StatusContract,
)
from personal_world.status import Status, worst  # noqa: E402
from personal_world.world import World  # noqa: E402

# ---------------------------------------------------------------------------
# Hand-rolled fakes (no unittest.mock)
# ---------------------------------------------------------------------------

class FakeHealthyProvider(StatusContract):
    def observe(self):
        return Result(ok=True, status="healthy", data={"provider": "fake"})


class FakeFailingProvider(StatusContract):
    def observe(self):
        return Result(ok=False, status="unavailable",
                      warnings=["connection refused"])


class FakeExplodingProvider(StatusContract):
    def observe(self):
        raise RuntimeError("provider crashed")


class FakeGarbageProvider(StatusContract):
    def observe(self):
        return "not a Result object"  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def registry() -> Registry:
    reg = Registry()
    reg.define_capability("source_control", StatusContract)
    return reg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCapabilityHealth:
    """Capability status reflects real provider evidence."""

    def test_healthy_returns_healthy(self, world: World):
        """A capability with a healthy observation reports HEALTHY."""
        prov = Provenance(source="test")
        world.register_capability(Capability(key="source_control"))
        world.record_fact(Fact(
            key="capability.source_control.status",
            value=Status.HEALTHY.value,
            provenance=prov,
        ))
        assert world.facts["capability.source_control.status"].value == Status.HEALTHY.value

    def test_unknown_when_no_check_has_run(self, world: World):
        """A registered capability with no observation is UNKNOWN (never guessed)."""
        world.register_capability(Capability(key="memory"))
        assert "capability.memory.status" not in world.facts


class TestProviderUnavailable:
    """Provider failure reports unavailable, never raises."""

    def test_failing_provider_reports_unavailable(self, registry: Registry):
        registry.register("source_control", "failing", FakeFailingProvider(),
                          health_check=lambda: False)
        result = registry.observe("source_control")
        assert not result.ok
        assert result.status == "unavailable"

    def test_exploding_provider_reports_unavailable(self, registry: Registry):
        """A provider that raises must be caught and reported as unavailable."""
        registry.register("source_control", "exploder", FakeExplodingProvider(),
                          health_check=lambda: True)
        result = registry.observe("source_control")
        assert not result.ok
        assert result.status == "unavailable"
        assert any("crashed" in w for w in result.warnings)


class TestStaleEvidence:
    """Old observations are flagged as stale."""

    def test_old_fact_is_stale(self, world: World):
        old_prov = Provenance(
            source="test",
            observed_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        world.record_fact(Fact(
            key="capability.discovery.status",
            value=Status.HEALTHY.value,
            provenance=old_prov,
        ))
        stale = world.stale_capabilities(60)
        assert "capability.discovery.status" in stale

    def test_fresh_fact_is_not_stale(self, world: World):
        fresh_prov = Provenance(source="test")  # uses now()
        world.record_fact(Fact(
            key="capability.memory.status",
            value=Status.HEALTHY.value,
            provenance=fresh_prov,
        ))
        stale = world.stale_capabilities(3600)
        assert "capability.memory.status" not in stale


class TestConflictingEvidence:
    """Two sources disagree; worst status wins."""

    def test_worst_status_wins(self):
        assert worst([Status.HEALTHY.value, Status.UNAVAILABLE.value]) == Status.UNAVAILABLE.value

    def test_unknown_better_than_unavailable(self):
        assert worst([Status.UNKNOWN.value, Status.UNAVAILABLE.value]) == Status.UNAVAILABLE.value

    def test_registry_picks_first_healthy_over_failing(self, registry: Registry):
        registry.register("source_control", "primary", FakeHealthyProvider(),
                          health_check=lambda: True)
        registry.register("source_control", "secondary", FakeFailingProvider(),
                          health_check=lambda: False)
        result = registry.observe("source_control")
        assert result.ok
        assert result.data["provider"] == "fake"


class TestBoringHealthy:
    """Nothing interesting to report; world says so."""

    def test_empty_world_summary(self, world: World):
        s = world.summary()
        assert s["facts"] == 0
        assert s["intents"] == 0
        assert s["policies"] == 0


class TestMalformedSource:
    """Garbage data fails safely."""

    def test_garbage_provider_returns_invalid_result(self, registry: Registry):
        registry.register("source_control", "garbage", FakeGarbageProvider(),
                          health_check=lambda: True)
        result = registry.observe("source_control")
        assert not result.ok
        assert result.status == "unavailable"
        assert any("invalid" in w for w in result.warnings)


class TestProvenance:
    """Every status carries source and observed_at."""

    def test_fact_carries_provenance(self, world: World):
        prov = Provenance(source="test:provenance_check")
        f = world.record_fact(Fact(
            key="capability.x.status",
            value=Status.HEALTHY.value,
            provenance=prov,
        ))
        assert f.provenance.source == "test:provenance_check"
        assert f.provenance.observed_at is not None

    def test_provenance_survives_roundtrip(self, world: World):
        prov = Provenance(source="test:roundtrip", provider="fake")
        f = world.record_fact(Fact(
            key="capability.y.status",
            value="healthy",
            provenance=prov,
        ))
        assert f.provenance.provider == "fake"
        assert f.provenance.authority == "observed"
