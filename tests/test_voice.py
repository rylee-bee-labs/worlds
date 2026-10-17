"""One voice + tone registers + the personality-pack gate (TRUE-NORTH
§ Voice, owner ruling 2026-09-22; Wave 1 Lane B).

Proves three rulings:
  1. the tone register is persisted via the existing prefs schema and
     actually reaches the model prompt;
  2. the residents / two-voice persona path only rides along when the
     personality pack is switched on (on by default since 2026-09-25);
  3. honest-off is unchanged — with no model configured, the endpoint
     still answers `not_configured` in every tone, and no tone block
     can remove the truth floor from the system prompt.
"""

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import crew, prefs, voice  # noqa: E402
from personal_world.chat import (
    ChatContract,  # noqa: E402
    build_chat_messages,  # noqa: E402
)
from personal_world.envelope import Result  # noqa: E402
from personal_world.world import World  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent


def _starter_state() -> dict:
    """The drawn roster, as the registry serves it (companion resolution is
    registry-backed since 2026-09-25 — see tests/test_companion_id.py)."""
    return {"crew": crew.starter_entries(), "keepers": {}}


class FakeChat(ChatContract):
    """Deterministic reference provider (same shape as test_chat.py's)."""

    def __init__(self, reply: str = "fake reply") -> None:
        self.reply = reply
        self.seen: list[list[dict]] = []

    def chat(self, messages):
        self.seen.append(messages)
        return Result(
            ok=True,
            status="healthy",
            data={"reply": self.reply, "thinking": None, "model": "fake"},
        )


class TestToneInstruction:
    """Every register produces a real instruction; unknown tones none."""

    @pytest.mark.parametrize("tone", voice.TONES)
    def test_each_register_has_an_instruction(self, tone):
        text = voice.tone_instruction(tone)
        assert text
        assert f"Tone register: {tone}." in text

    @pytest.mark.parametrize("tone", voice.TONES)
    def test_every_register_carries_the_truth_sentence(self, tone):
        # Honesty floor is register-independent: the same truth sentence
        # rides in every tone, so no register can talk the model out of
        # labeling degraded states honestly.
        assert "facts, statuses, and uncertainty stay exact" in (
            voice.tone_instruction(tone)
        )

    @pytest.mark.parametrize("tone", [None, "", "sarcastic", "WARM", 42])
    def test_unknown_tone_degrades_to_no_block(self, tone):
        assert voice.tone_instruction(tone) == ""


class TestResolveVoice:
    """Preference resolution: one voice by default, pack gated."""

    def test_defaults_are_one_voice_warm(self):
        sel = voice.resolve_voice(None)
        assert sel == voice.VoiceSelection(persona=None, tone="warm")
        assert voice.resolve_voice({}) == sel

    def test_tone_pref_is_respected(self):
        assert voice.resolve_voice({"tone": "concise"}).tone == "concise"

    def test_invalid_tone_falls_back_to_warm(self):
        assert voice.resolve_voice({"tone": "vengeful"}).tone == "warm"

    def test_pack_off_gates_the_resident_persona(self):
        # The historical behavior was: companion pref -> persona always.
        # With the pack off (default) the companion pref is stored but
        # NOT routed into the prompt — one voice is the default.
        sel = voice.resolve_voice(
            {"personality_pack": "off", "companion": "mermaid"}
        )
        assert sel.persona is None

    def test_pack_absent_gates_the_resident_persona(self):
        sel = voice.resolve_voice({"companion": "mermaid"})
        assert sel.persona is None

    def test_pack_on_restores_the_residents_path(self):
        # The kept canon path still works behind the flag — now resolved
        # through the crew registry (owner decision 2026-09-25): the legacy
        # `mermaid` value migrates to the starter `renai`, whose canon names
        # the shipped persona template. Without a roster there is nothing to
        # confirm the companion exists, so the fail-safe is the one voice.
        sel = voice.resolve_voice(
            {"personality_pack": "residents", "companion": "mermaid"},
            _starter_state(),
        )
        assert sel.persona == "mermaid"
        assert sel.companion.id == "renai"
        # Tone still applies with the pack on — crew voice is flavor
        # over the one voice's register, never a replacement.
        assert sel.tone == "warm"

    def test_pack_on_without_companion_stays_one_voice(self):
        sel = voice.resolve_voice(
            {"personality_pack": "residents"}, _starter_state()
        )
        assert sel.persona is None
        assert sel.companion is None

    def test_sol_is_voiceless_even_with_the_pack_on(self):
        # Owner, 2026-09-25: Sol is the Worlds mark, not a companion —
        # choosing her keeps the one plain voice.
        sel = voice.resolve_voice(
            {"personality_pack": "residents", "companion": "personal-world"},
            _starter_state(),
        )
        assert sel.persona is None
        assert sel.companion is None

    def test_resolve_from_real_prefs_round_trip(self):
        # The default is now the one voice: `companion_id` is unset, so the
        # old `assistant` default names no crew entry and adds no persona
        # (companions addendum item 4).
        w = World()
        prefs.set_prefs(w, {"tone": "playful", "personality_pack": "residents"})
        sel = voice.resolve_voice(prefs.get_prefs(w), _starter_state())
        assert sel.tone == "playful"
        assert sel.persona is None
        assert sel.companion is None


class TestPrefsVocabulary:
    """The new keys live in the existing schema, additive and floored."""

    def test_tone_vocab(self):
        assert prefs.TONE.allowed == ("warm", "concise", "playful", "formal")
        assert prefs.TONE.default == "warm"

    def test_pack_vocab(self):
        assert prefs.PERSONALITY_PACK.allowed == ("off", "residents")
        # Owner, 2026-09-25: "turn it on" — the crew is on by default;
        # "off" stays available and is the fail-safe for missing values.
        assert prefs.PERSONALITY_PACK.default == "residents"

    def test_off_vocabulary_tone_rejected(self):
        with pytest.raises(prefs.PrefsValueError, match="tone"):
            prefs.set_prefs(World(), {"tone": "haughty"})

    def test_off_vocabulary_pack_rejected(self):
        with pytest.raises(prefs.PrefsValueError, match="personality_pack"):
            prefs.set_prefs(World(), {"personality_pack": True})

    def test_existing_keys_untouched(self):
        # Additive only: the accessibility-floor keys keep their shape.
        assert prefs.MOTION.default == "reduced"
        assert prefs.TARGET_SIZE.default == 44
        assert prefs.COMPANION.default == "assistant"


class TestBuildChatMessagesTone:
    """The tone block sits above the identity floor, never replaces it."""

    def test_tone_block_present_and_floor_intact(self):
        msgs = build_chat_messages("hi", "ctx", tone="concise")
        system = msgs[0]["content"]
        assert "Tone register: concise." in system
        assert system.index("Tone register: concise.") < system.index(
            "You are the Worlds assistant"
        )
        # The floor survives every tone: truth rule + status vocabulary.
        assert "ONLY the context block below" in system
        assert "not_configured" in system

    def test_no_tone_means_no_block_and_floor_intact(self):
        system = build_chat_messages("hi", "ctx")[0]["content"]
        assert "Tone register:" not in system
        assert "You are the Worlds assistant" in system

    def test_unknown_tone_adds_nothing(self):
        system = build_chat_messages("hi", "ctx", tone="bogus")[0]["content"]
        assert "Tone register:" not in system

    @pytest.mark.parametrize("tone", voice.TONES)
    def test_every_register_keeps_the_truth_rules(self, tone):
        system = build_chat_messages("hi", "ctx", tone=tone)[0]["content"]
        assert "instead of inventing status" in system
        assert "facts, statuses, and uncertainty stay exact" in system


# ── Endpoint level: the pref actually drives the prompt ──────────────


@pytest.fixture
def chat_client(tmp_path, monkeypatch):
    """App with a fake reasoning provider AND the shipped prompt tree
    copied in, so persona-template routing is exercised for real."""
    from fastapi.testclient import TestClient

    import personal_world.api as api_mod

    monkeypatch.setenv("PW_API_TOKEN", "t")
    shutil.copytree(REPO_ROOT / "config" / "prompts", tmp_path / "prompts")

    fake = FakeChat(reply="ok")
    real_build_registry = api_mod.build_registry

    def patched_build_registry(world, registry, config_dir, **kwargs):
        reg = real_build_registry(world, registry, config_dir, **kwargs)
        reg.register(
            "reasoning", "fake-chat", fake, health_check=lambda: True,
            writes="none",
        )
        return reg

    monkeypatch.setattr(api_mod, "build_registry", patched_build_registry)
    client = TestClient(api_mod.create_app(tmp_path, tmp_path))
    client.headers.update({"Authorization": "Bearer t"})
    return client, fake


def _system_prompt(fake: FakeChat) -> str:
    return fake.seen[-1][0]["content"]


class TestChatEndpointVoice:
    def test_default_pack_is_residents(self, chat_client):
        c, _ = chat_client
        r = c.get("/api/prefs")
        assert r.status_code == 200
        assert r.json()["data"]["personality_pack"] == "residents"

    def test_pack_off_is_one_voice_warm(self, chat_client):
        c, fake = chat_client
        assert (
            c.put("/api/prefs", json={"personality_pack": "off"}).status_code
            == 200
        )
        r = c.post("/api/chat", json={"message": "hi"})
        assert r.status_code == 200 and r.json()["ok"] is True
        system = _system_prompt(fake)
        assert "Tone register: warm." in system
        # Pack off: no resident persona in the prompt even though the
        # companion pref has a stored default.
        assert "You speak as Mermaid" not in system
        assert "You speak as Personal World" not in system

    def test_tone_pref_reaches_the_prompt(self, chat_client):
        c, fake = chat_client
        assert c.put("/api/prefs", json={"tone": "formal"}).status_code == 200
        r = c.post("/api/chat", json={"message": "hi"})
        assert r.status_code == 200 and r.json()["ok"] is True
        assert "Tone register: formal." in _system_prompt(fake)

    def test_companion_pref_alone_does_not_add_a_persona(self, chat_client):
        c, fake = chat_client
        assert (
            c.put(
                "/api/prefs",
                json={"companion": "mermaid", "personality_pack": "off"},
            ).status_code
            == 200
        )
        c.post("/api/chat", json={"message": "hi"})
        assert "You speak as Mermaid" not in _system_prompt(fake)

    def test_pack_on_routes_the_resident_persona(self, chat_client):
        c, fake = chat_client
        assert (
            c.put(
                "/api/prefs",
                json={"personality_pack": "residents", "companion": "mermaid"},
            ).status_code
            == 200
        )
        c.post("/api/chat", json={"message": "hi"})
        system = _system_prompt(fake)
        # The kept residents path still works, unchanged, behind the flag.
        assert "You speak as Mermaid" in system
        # …and the truth floor still leads/anchors it.
        assert "You are the Worlds assistant" in system
        assert "Tone register: warm." in system

    def test_pack_off_again_removes_the_persona(self, chat_client):
        c, fake = chat_client
        # A chosen companion (Renai) speaks through her kept canon persona
        # template while the pack is on…
        c.put(
            "/api/prefs",
            json={"personality_pack": "residents", "companion_id": "renai"},
        )
        c.post("/api/chat", json={"message": "hi"})
        assert "You speak as" in _system_prompt(fake)
        # …and the pack off removes it again, one voice only.
        c.put("/api/prefs", json={"personality_pack": "off"})
        c.post("/api/chat", json={"message": "again"})
        assert "You speak as" not in _system_prompt(fake)


class TestHonestOffUnchanged:
    """Model-off: same outcomes, honest label — in every tone."""

    @pytest.fixture
    def bare_client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app

        monkeypatch.setenv("PW_API_TOKEN", "t")
        c = TestClient(create_app(tmp_path, tmp_path))
        c.headers.update({"Authorization": "Bearer t"})
        return c

    @pytest.mark.parametrize("tone", list(voice.TONES) + [None])
    def test_no_provider_is_still_not_configured(self, bare_client, tone):
        c = bare_client
        if tone is not None:
            assert c.put("/api/prefs", json={"tone": tone}).status_code == 200
        r = c.post("/api/chat", json={"message": "hi"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"
        assert "no chat provider configured" in body["warnings"][0]

    def test_pack_flag_never_fakes_a_reply(self, bare_client):
        c = bare_client
        assert (
            c.put(
                "/api/prefs",
                json={"personality_pack": "residents", "companion": "mermaid"},
            ).status_code
            == 200
        )
        r = c.post("/api/chat", json={"message": "hi"})
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"
