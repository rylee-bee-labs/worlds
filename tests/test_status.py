import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.model import Fact, Provenance  # noqa: E402
from personal_world.status import RANK, Status, worst  # noqa: E402
from personal_world.world import World  # noqa: E402


class TestStatusEnum:
    def test_all_statuses_roundtrip(self):
        for s in Status:
            assert s.value == str(s)
            assert Status(s.value) == s

    def test_rank_order(self):
        assert RANK[Status.HEALTHY.value] == 0
        assert RANK[Status.WARNING.value] == 1
        assert RANK[Status.UNKNOWN.value] == 2
        assert RANK[Status.NEEDS_ATTENTION.value] == 3
        assert RANK[Status.UNAVAILABLE.value] == 4
        assert RANK[Status.STALE.value] == 5
        assert RANK[Status.DISABLED.value] == 6
        assert RANK[Status.NOT_CONFIGURED.value] == 7

    def test_rank_unknown_between_healthy_and_unavailable(self):
        assert RANK[Status.HEALTHY.value] < RANK[Status.UNKNOWN.value]
        assert RANK[Status.UNKNOWN.value] < RANK[Status.UNAVAILABLE.value]


class TestWorst:
    def test_empty_list_returns_healthy(self):
        assert worst([]) == Status.HEALTHY.value

    def test_single_item_returns_itself(self):
        assert worst([Status.HEALTHY.value]) == Status.HEALTHY.value
        assert worst([Status.UNAVAILABLE.value]) == Status.UNAVAILABLE.value

    def test_higher_rank_wins(self):
        assert worst([Status.HEALTHY.value, Status.UNAVAILABLE.value]) == Status.UNAVAILABLE.value
        assert worst([Status.NEEDS_ATTENTION.value, Status.UNKNOWN.value]) == Status.NEEDS_ATTENTION.value
        assert worst([Status.WARNING.value, Status.NOT_CONFIGURED.value, Status.HEALTHY.value]) == Status.NOT_CONFIGURED.value

    def test_unknown_better_than_unavailable(self):
        assert worst([Status.UNKNOWN.value, Status.UNAVAILABLE.value]) == Status.UNAVAILABLE.value


class TestStaleCapabilities:
    def test_old_fact_is_stale(self):
        w = World()
        old_prov = Provenance(
            source="test",
            observed_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        w.record_fact(Fact(
            key="capability.discovery.status",
            value="healthy",
            provenance=old_prov,
        ))
        stale = w.stale_capabilities(60)
        assert "capability.discovery.status" in stale

    def test_fresh_fact_is_not_stale(self):
        w = World()
        fresh_prov = Provenance(source="test")  # uses now()
        w.record_fact(Fact(
            key="capability.memory.status",
            value="healthy",
            provenance=fresh_prov,
        ))
        stale = w.stale_capabilities(3600)  # 1 hour threshold
        assert "capability.memory.status" not in stale

    def test_non_capability_facts_ignored(self):
        w = World()
        old_prov = Provenance(
            source="test",
            observed_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        w.record_fact(Fact(
            key="service.something.version",
            value="1.0",
            provenance=old_prov,
        ))
        w.record_fact(Fact(
            key="random.key",
            value="x",
            provenance=old_prov,
        ))
        stale = w.stale_capabilities(60)
        assert stale == []

    def test_mixed_fresh_and_old(self):
        w = World()
        old_prov = Provenance(
            source="test",
            observed_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        fresh_prov = Provenance(source="test")
        w.record_fact(Fact(
            key="capability.discovery.status",
            value="healthy",
            provenance=old_prov,
        ))
        w.record_fact(Fact(
            key="capability.memory.status",
            value="healthy",
            provenance=fresh_prov,
        ))
        stale = w.stale_capabilities(60)
        assert "capability.discovery.status" in stale
        assert "capability.memory.status" not in stale
