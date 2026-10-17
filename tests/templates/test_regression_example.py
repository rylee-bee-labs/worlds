"""Template: regression tests.

Minimal structure for protecting against specific past failures.
Copy, fill in, and never delete — these are cheap insurance.

Pattern:
    1. Describe what broke and how it was fixed (module docstring).
    2. Reproduce the bad behavior in the test.
    3. Assert the fix works.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from personal_world.model import (  # noqa: E402
    Mutability,
    Override,
    Policy,
    PolicyEffect,
    Provenance,
)
from personal_world.world import MutationDenied, World  # noqa: E402

# ---------------------------------------------------------------------------
# Filled-in example (not just comments)
# ---------------------------------------------------------------------------

"""Regression: cemented policy was overridable by pack install

This test protects against packs silently flipping a cemented deny to allow.

Before the fix: install_pack() would overwrite a cemented policy because it
    only checked for existing policies of the same key, not their mutability.
After the fix: cemented policies are never touched by pack install; the
    existing cemented policy survives unchanged.
"""


def test_cemented_policy_survives_pack_install():
    """Pack install must not overwrite a cemented deny policy."""
    w = World()
    prov = Provenance(source="user:explicit")
    w.set_policy(Policy(
        key="content.animal_cruelty",
        effect=PolicyEffect.DENY,
        override=Override.EXPLICIT_USER_REQUEST_ONLY,
        provenance=prov,
    ))
    w.cement("content.animal_cruelty")

    # The attack: a malicious pack tries to flip the policy to allow.
    from personal_world.model import Pack
    w.install_pack(Pack(key="evil-pack", policies={
        "content.animal_cruelty": {"effect": "allow"},
    }))

    # The fix: cemented policy still says deny.
    assert w.check_policy("content.animal_cruelty") == "deny"
    assert w.policies["content.animal_cruelty"].mutability == Mutability.CEMENTED


"""Regression: suggested lore was silently confirmable by providers

This test protects against provider output promoting suggested lore to
confirmed without an explicit user action.

Before the fix: promote_lore() did not check the actor, so a provider
    calling promote_lore(key, CONFIRMED) would succeed silently.
After the fix: promotion to CONFIRMED requires an explicit UserAction;
    without one, MutationDenied is raised.
"""


def test_suggested_lore_requires_user_action_to_confirm():
    """Provider output must not silently confirm suggested lore."""
    from personal_world.model import Lore, LoreState
    w = World()
    prov = Provenance(source="ai:inference")
    w.add_lore(Lore(
        key="preference.dark_mode",
        value="enabled",
        state=LoreState.SUGGESTED,
        provenance=prov,
    ))

    with pytest.raises(MutationDenied):
        w.promote_lore("preference.dark_mode", LoreState.CONFIRMED)


"""Regression: unknown policy was treated as allow

This test protects against the check_policy() method returning 'allow'
for policies that were never registered.

Before the fix: check_policy() returned 'allow' as a default when no
    policy existed for a key.
After the fix: check_policy() returns 'unknown' for unregistered keys,
    and downstream code must handle unknown explicitly.
"""


def test_unknown_policy_returns_unknown_not_allow():
    """Unregistered policy must return 'unknown', never 'allow'."""
    w = World()
    assert w.check_policy("content.does_not_exist") == "unknown"
    assert w.check_policy("content.does_not_exist") != "allow"


# ---------------------------------------------------------------------------
# Blank template for contributors to copy
# ---------------------------------------------------------------------------

"""Regression: <describe what broke and how it was fixed>

This test protects against <the specific failure mode>.

Before the fix: <what happened>
After the fix: <what should happen>
"""


def test_regression_template():
    """<descriptive name matching the failure mode>"""
    # 1. Reproduce the bad behavior (set up the preconditions).
    w = World()

    # 2. Trigger the path that used to break.
    result = w.check_policy("content.nonexistent")

    # 3. Assert the fix works.
    assert result == "unknown"
