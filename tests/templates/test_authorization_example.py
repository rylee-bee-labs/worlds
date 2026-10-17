"""Template: testing action/authorization boundaries.

The brain may propose. The authoritative capability/action layer decides.

Invariants protected:
    - Allowed action:      user action succeeds through the world gate.
    - Denied action:       cemented policy rejects non-user mutation.
    - Brain suggestion:    model proposes, world decides (never the reverse).
    - Malformed arguments: missing required field fails safely.
    - Missing info:        UNKNOWN state, not guessed.
    - Failed action:       provider error handled safely.
    - Partial success:     honest reporting of partial results.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from personal_world.envelope import Result  # noqa: E402
from personal_world.model import (  # noqa: E402
    Fact,
    Lore,
    LoreState,
    Override,
    Policy,
    PolicyEffect,
    Provenance,
)
from personal_world.providers.registry import Registry, StatusContract  # noqa: E402
from personal_world.world import MutationDenied, UserAction, World  # noqa: E402

# ---------------------------------------------------------------------------
# Hand-rolled fakes
# ---------------------------------------------------------------------------

class FakeAllowedAction(StatusContract):
    """Simulates a provider that succeeds."""

    def observe(self):
        return Result(ok=True, status="healthy", data={"action": "executed"})


class FakeDeniedAction(StatusContract):
    """Simulates a provider that refuses the action."""

    def observe(self):
        return Result(ok=False, status="denied",
                      warnings=["policy forbids this action"])


class FakeBrokenAction(StatusContract):
    """Simulates a provider that blows up mid-action."""

    def observe(self):
        raise ConnectionError("downstream service unreachable")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def cemented_world() -> World:
    """World with a cemented deny policy."""
    w = World()
    prov = Provenance(source="user:explicit")
    w.set_policy(Policy(
        key="content.animal_cruelty",
        effect=PolicyEffect.DENY,
        override=Override.EXPLICIT_USER_REQUEST_ONLY,
        provenance=prov,
    ))
    w.cement("content.animal_cruelty")
    return w


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAllowedAction:
    """User action succeeds through the world gate."""

    def test_user_can_set_own_intent(self, world: World):
        prov = Provenance(source="user:action")
        world.set_intent(Fact(
            key="service.plex.version",
            value="1.40.0",
            provenance=prov,
        ))
        assert world.intents["service.plex.version"].value == "1.40.0"

    def test_user_can_confirm_own_lore(self, world: World):
        prov = Provenance(source="user:explicit")
        world.add_lore(Lore(
            key="preference.genre",
            value="mystery",
            state=LoreState.SUGGESTED,
            provenance=prov,
        ))
        world.promote_lore("preference.genre", LoreState.CONFIRMED,
                           actor=UserAction())
        assert world.lore["preference.genre"].state == LoreState.CONFIRMED


class TestDeniedAction:
    """Cemented policy rejects non-user mutation."""

    def test_cemented_policy_blocks_ai_mutation(self, cemented_world: World):
        with pytest.raises(MutationDenied):
            cemented_world.set_policy(Policy(
                key="content.animal_cruelty",
                effect=PolicyEffect.ALLOW,
                provenance=Provenance(source="ai:brain"),
            ))

    def test_cemented_policy_blocks_import_mutation(self, cemented_world: World):
        with pytest.raises(MutationDenied):
            cemented_world.set_policy(Policy(
                key="content.animal_cruelty",
                effect=PolicyEffect.ALLOW,
                provenance=Provenance(source="import:evil-pack"),
            ))

    def test_cemented_policy_allows_explicit_user(self, cemented_world: World):
        cemented_world.set_policy(
            Policy(
                key="content.animal_cruelty",
                effect=PolicyEffect.ALLOW,
                provenance=Provenance(source="user:explicit"),
            ),
            actor=UserAction(confirmed=True),
        )
        assert cemented_world.check_policy("content.animal_cruelty") == "allow"


class TestBrainSuggestion:
    """Model proposes, world decides (never the reverse)."""

    def test_suggested_lore_cannot_self_confirm(self, world: World):
        """AI-suggested lore must not silently promote itself to confirmed."""
        world.add_lore(Lore(
            key="taste.dark_mode",
            value="enabled",
            state=LoreState.SUGGESTED,
            provenance=Provenance(source="ai:inference"),
        ))
        with pytest.raises(MutationDenied):
            world.promote_lore("taste.dark_mode", LoreState.CONFIRMED)

    def test_unknown_policy_is_never_allow(self, world: World):
        """An unregistered policy returns 'unknown', never silently allows."""
        assert world.check_policy("content.nonexistent") == "unknown"


class TestMalformedArguments:
    """Missing required field fails safely."""

    def test_fact_without_provenance_rejected(self, world: World):
        """Pydantic validation catches missing provenance at construction."""
        with pytest.raises(ValueError):
            Fact(key="x", value="y", provenance=None)  # type: ignore[arg-type]

    def test_policy_without_effect_rejected(self, world: World):
        with pytest.raises(ValueError):
            Policy(key="x", provenance=Provenance(source="test"))  # type: ignore[call-arg]


class TestMissingInformation:
    """UNKNOWN state, not guessed."""

    def test_unregistered_capability_is_unknown(self, world: World):
        assert world.check_policy("capability.unregistered") == "unknown"

    def test_empty_lore_dict(self, world: World):
        assert world.lore == {}

    def test_missing_provider_returns_not_configured(self):
        reg = Registry()
        result = reg.observe("nonexistent")
        assert not result.ok
        assert result.status == "not_configured"


class TestFailedAction:
    """Provider error handled safely."""

    def test_broken_provider_reports_unavailable(self):
        reg = Registry()
        reg.define_capability("test_cap", StatusContract)
        reg.register("test_cap", "broken", FakeBrokenAction(),
                     health_check=lambda: True)
        result = reg.observe("test_cap")
        assert not result.ok
        assert result.status == "unavailable"
        assert any("unreachable" in w for w in result.warnings)


class TestPartialSuccess:
    """Honest reporting of partial results."""

    def test_registry_substitutes_when_primary_unhealthy(self):
        reg = Registry()
        reg.define_capability("source_control", StatusContract)
        reg.register("source_control", "primary", FakeDeniedAction(),
                     health_check=lambda: False)
        reg.register("source_control", "fallback", FakeAllowedAction(),
                     health_check=lambda: True)
        result = reg.observe("source_control")
        assert result.ok
        assert result.data["action"] == "executed"
