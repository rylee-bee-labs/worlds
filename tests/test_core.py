import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.classification import Classification  # noqa: E402
from personal_world.envelope import Result  # noqa: E402
from personal_world.export import settings_export, world_export  # noqa: E402
from personal_world.journal import Journal  # noqa: E402
from personal_world.model import (  # noqa: E402
    Fact,
    Intent,
    JournalKind,
    Lore,
    LoreState,
    Mutability,
    Override,
    Pack,
    Policy,
    PolicyEffect,
    Provenance,
)
from personal_world.providers.adapters import (  # noqa: E402
    FakeSourceControl,
    Gitea,
)
from personal_world.providers.registry import Registry  # noqa: E402
from personal_world.world import MutationDenied, UserAction, World  # noqa: E402

FAKE_SENSITIVE = {
    "name": "Example Person",
    "email": "person@example.invalid",
    "token": "synthetic-token-for-tests-only",  # pw-safety: synthetic
    "password": "correct-horse-battery-staple",  # pw-safety: synthetic
    "private_lore": "Example Person's private narrative that must never leak",
    "api_key": "synthetic-api-key-for-tests-only",  # pw-safety: synthetic
}


@pytest.fixture
def world() -> World:
    return World()


def seeded_world() -> World:
    """A world deliberately stuffed with fake sensitive data in every
    record class, to prove exports cannot leak it."""
    w = World()
    prov = Provenance(source="test")
    w.record_fact(Fact(
        key="service.plex.version",
        value="1.2.3",
        provenance=prov,
        classification=Classification.PRIVATE,
    ))
    w.record_fact(Fact(
        key="leak.canary",
        value=FAKE_SENSITIVE["token"],
        provenance=prov,
        classification=Classification.SECRET,
    ))
    w.set_intent(Intent(
        key="service.plex.version",
        value="1.2.3",
        provenance=prov,
    ))
    w.set_policy(Policy(
        key="content.animal_cruelty",
        effect=PolicyEffect.DENY,
        override=Override.EXPLICIT_USER_REQUEST_ONLY,
        mutability=Mutability.CEMENTED,
        provenance=prov,
    ))
    w.add_lore(Lore(
        key="identity.canary",
        value=FAKE_SENSITIVE["private_lore"],
        state=LoreState.CONFIRMED,
        provenance=prov,
        classification=Classification.PRIVATE,
    ))
    w.add_lore(Lore(
        key="preference.mysteries",
        value="user likes mysteries",
        state=LoreState.CONFIRMED,
        provenance=prov,
        classification=Classification.WORLD,
    ))
    return w


class TestSettingsExportSafety:
    """Core acceptance: settings-export is structurally incapable of
    carrying private/secret/identifying data."""

    def test_no_sensitive_fixture_values_in_settings_export(self):
        blob = json.dumps(settings_export(seeded_world()))
        for label, value in FAKE_SENSITIVE.items():
            assert value not in blob, f"LEAK: {label} appeared in settings-export"

    def test_settings_export_contains_no_facts_intent_or_lore(self):
        sx = settings_export(seeded_world())
        assert "facts" not in sx
        assert "intents" not in sx
        assert "lore" not in sx

    def test_settings_export_still_describes_architecture(self):
        w = seeded_world()
        from personal_world.model import Capability, Provider
        w.register_capability(Capability(key="source_control"))
        w.map_provider(Provider(
            capability="source_control", name="gitea", writes="none",
            requires_secrets=["gitea/token"],
        ))
        sx = settings_export(w)
        assert sx["schema"] == "personal-world/settings-export/1"
        assert any(c["key"] == "source_control" for c in sx["capabilities"])

    def test_cemented_policy_appears_but_only_as_rule(self):
        sx = settings_export(seeded_world())
        pol = [p for p in sx["policies"] if p["key"] == "content.animal_cruelty"]
        assert pol and pol[0]["effect"] == "deny"
        assert pol[0]["mutability"] == "cemented"


class TestCementedPolicy:
    def test_cemented_policy_rejects_non_user_mutation(self):
        w = seeded_world()
        with pytest.raises(MutationDenied):
            w.set_policy(Policy(
                key="content.animal_cruelty",
                effect=PolicyEffect.ALLOW,  # the attack: AI/provider/import flips it
                override=Override.NONE,
                provenance=Provenance(source="import:malicious-pack"),
            ))

    def test_cemented_policy_accepts_explicit_user_action(self):
        w = seeded_world()
        w.set_policy(
            Policy(
                key="content.animal_cruelty",
                effect=PolicyEffect.ALLOW,
                override=Override.NONE,
                provenance=Provenance(source="user:explicit"),
            ),
            actor=UserAction(confirmed=True),
        )
        assert w.check_policy("content.animal_cruelty") == "allow"

    def test_cement_command_requires_user_actor(self):
        w = seeded_world()
        with pytest.raises(MutationDenied):
            w.promote_lore("identity.canary", LoreState.CONFIRMED)  # no-op path check

    def test_pack_cannot_override_user_policy(self):
        w = seeded_world()
        pack = Pack(key="evil-pack", policies={
            "content.animal_cruelty": {"effect": "allow"},
        })
        w.install_pack(pack)
        assert w.check_policy("content.animal_cruelty") == "deny"

    def test_pack_policies_land_as_normal_defaults(self):
        w = World()
        w.install_pack(Pack(key="p", policies={
            "content.gore": {"effect": "deny"},
        }))
        p = w.policies["content.gore"]
        assert p.mutability == Mutability.NORMAL
        assert p.provenance.source == "pack:p"

    def test_unknown_policy_is_unknown_never_allow(self):
        w = World()
        assert w.check_policy("content.unknown_thing") == "unknown"


class TestLorePromotion:
    def test_suggested_never_confirms_silently(self):
        w = seeded_world()
        w.add_lore(Lore(key="t", value="x", state=LoreState.SUGGESTED,
                        provenance=Provenance(source="ai")))
        with pytest.raises(MutationDenied):
            w.promote_lore("t", LoreState.CONFIRMED)

    def test_user_can_confirm_suggested(self):
        w = seeded_world()
        w.add_lore(Lore(key="t", value="x", state=LoreState.SUGGESTED,
                        provenance=Provenance(source="ai")))
        w.promote_lore("t", LoreState.CONFIRMED, actor=UserAction())
        assert w.lore["t"].state == LoreState.CONFIRMED

    def test_confirmed_cannot_revert(self):
        w = seeded_world()
        with pytest.raises(MutationDenied):
            w.promote_lore("preference.mysteries", LoreState.SUGGESTED,
                          actor=UserAction())


class TestWorldExport:
    def test_world_export_has_no_private_lore(self):
        wx = world_export(seeded_world())
        assert "identity.canary" not in json.dumps(wx)
        assert "preference.mysteries" in wx["lore"]

    def test_world_export_never_contains_secret_facts(self):
        wx = world_export(seeded_world())
        blob = json.dumps(wx)
        for label, value in FAKE_SENSITIVE.items():
            if label in ("name", "email"):
                continue  # world-export is personal data by contract
            assert value not in blob, f"LEAK: {label} in world-export"


class TestProviderSubstitution:
    def test_gitea_and_fake_share_contract(self):
        reg = Registry()
        reg.define_capability("source_control", Gitea.__mro__[1])
        real = Gitea("http://service.example.invalid:3000")
        fake = FakeSourceControl()
        reg.register("source_control", "gitea", real,
                     health_check=lambda: False, writes="none")
        reg.register("source_control", "fake", fake,
                     health_check=lambda: True, writes="none")
        # unhealthy real provider -> fake substitutes transparently
        r = reg.observe("source_control")
        assert r.ok
        assert r.data["provider"] == "fake"

    def test_registry_fails_closed_on_missing_capability(self):
        reg = Registry()
        r = reg.observe("nothing")
        assert not r.ok
        assert r.status == "not_configured"

    def test_provider_exception_reports_unavailable(self):
        class Exploding:
            def observe(self):
                raise RuntimeError("boom")
        reg = Registry()
        reg.define_capability("x", object)
        reg.register("x", "exploder", Exploding())
        r = reg.observe("x")
        assert not r.ok and r.status == "unavailable"


class TestEnvelope:
    def test_result_shape(self):
        r = Result(ok=True, status="healthy")
        d = json.loads(r.model_dump_json())
        assert set(d) >= {"ok", "status", "changed", "warnings", "actions"}


class TestJournal:
    def test_journal_roundtrip_and_story_redaction(self, tmp_path):
        j = Journal(tmp_path / "j.ndjson")
        j.record(JournalKind.OBSERVATION, "public observation", "test",
                classification=Classification.WORLD)
        j.record(JournalKind.SECURITY, FAKE_SENSITIVE["private_lore"], "test",
                classification=Classification.PRIVATE)
        assert len(list(j.events())) == 2
        from personal_world.export import story_export
        story = story_export(j)
        assert FAKE_SENSITIVE["private_lore"] not in story
        assert "public observation" in story
